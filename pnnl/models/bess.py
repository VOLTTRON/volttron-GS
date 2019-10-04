import itertools
import numpy as np
import pandas
import pulp
import logging
import importlib
import variable_group
from variable_group import VariableGroup, RANGE
from volttron.platform.agent import utils

BESS_AVAILABLE = True

_log = logging.getLogger(__name__)
utils.setup_logging()

class bess(object):
    def __init__(self, config, parent, **kwargs):
        # BESS CONSTANTS --- should be config parameters
        self.MESA1_C0 = config.get("MESA1_C0", -1.44E-02)  # unit: 1/h
        self.MESA1_C_p = config.get("MESA1_C_p", -9.38E-04)  # unit: 1/kWh
        self.MESA1_C_n = config.get("MESA1_C_n", -9.22E-04)  # unit: 1/kWht_UB_range
        self.p_max = config.get("p_max", 1.0)
        self.init_soc = config.get("init_soc", 0.8)
        self.final_soc = config.get("final_soc", -1.0)

    def build_bess_constraints(self, energy_price, reserve_price):
        """
        Build constraints and objective function for BESS
        :param energy_price: Energy price from city market
        :param reserve_price: Reserve price from city market
        :param p_max: maximum charging/discharging power of BESS
        :param init_soc:
        :param final_soc:
        :return:
        """
        numHours = len(energy_price)
        if numHours != len(reserve_price):
            raise (TypeError("The lengths of energy_price, reserve_price should match."))

        print("EnergyPrice: {}".format(energy_price))
        print("ReservePrice: {}".format(reserve_price))
        print("p_max: {}".format(self.p_max))
        print("init_soc: {}".format(self.init_soc))
        print("final_soc: {}".format(self.final_soc))

        numHours_range = (range(numHours),)
        n2_range = (range(numHours + 1),)

        def constant(x):
            def _constant(*args, **kwargs):
                return x

            return _constant

        constant_zero = constant(0.0)
        constant_pos_one = constant(1.0)

        bess_p_p = VariableGroup("bess_p_p", indexes=numHours_range, lower_bound_func=constant_zero,
                                 base_name="Power injection (MW)")  # Power injection into the grid, or battery discharging (non-negative)
        bess_p_n = VariableGroup("bess_p_n", indexes=numHours_range, upper_bound_func=constant_zero,
                                 base_name="Power withdrawal (MW)")  # Power withdrawal from the grid, or battery charging (non-positive)
        bess_b = VariableGroup("bess_b", indexes=numHours_range, is_binary_var=True,
                               base_name="Power withdrawal (MW)")  # 1 == Discharging, 0 == Charging
        bess_p = VariableGroup("bess_p", indexes=numHours_range,
                               base_name="Net power transfer (MW)")  # power transfer from battery to grid
        bess_l = VariableGroup("bess_l", indexes=n2_range, lower_bound_func=constant_zero,
                               upper_bound_func=constant_pos_one,
                               base_name="State of charge")  # State of charge (SoC) in [0, 1]
        bess_r_p = VariableGroup("bess_r_p", indexes=numHours_range,
                                 base_name="Reserve power (MW)")  # Reserve power (non-negative)

        # CONSTRAINTS
        constraints = []

        def add_constraint(name, indexes, constraint_func):
            name_base = name
            for _ in range(len(indexes)):
                name_base += "_{}"

            for index in itertools.product(*indexes):
                name = name_base.format(*index)
                c = constraint_func(index)

                constraints.append((c, name))

        name = 'bess_engy_intial_condition'

        def checkInitSoC(index):
            return bess_l[index] == init_soc

        c = checkInitSoC(0)
        constraints.append((c, name))

        if final_soc >= 0:
            name = 'bess_engy_final_condition'

            def checkFinalSoC(index):
                return bess_l[index] == final_soc

            c = checkFinalSoC(numHours)
            constraints.append((c, name))

        numHours_index = (range(numHours),)

        def engy_dynamics_func(index):
            k = index[0]
            return bess_l[k + 1] - bess_l[k] == self.MESA1_C0 + (
                        self.MESA1_C_p * bess_p_p[k] + self.MESA1_C_n * bess_p_n[k]) * 1000  # 1000 kW / MW

        add_constraint("bess_engy_dynamics", numHours_index, engy_dynamics_func)

        def discharge_cap_func(index):
            k = index[0]
            return bess_p_p[k] <= p_max * bess_b[k]

        add_constraint("bess_discharge_cap", numHours_index, discharge_cap_func)

        def charge_cap_func(index):
            k = index[0]
            return -p_max * (1 - bess_b[k]) <= bess_p_n[k]

        add_constraint("bess_charge_cap", numHours_index, charge_cap_func)

        def pow_transfer_func(index):
            k = index[0]
            return bess_p[k] == bess_p_p[k] + bess_p_n[k]

        add_constraint("bess_pow_transfer", numHours_index, pow_transfer_func)

        def reg_up_nng_func(index):
            k = index[0]
            return bess_r_p[k] >= 0.0

        add_constraint("bess_reg_up_nng", numHours_index, reg_up_nng_func)

        def reg_up_cap_func(index):
            k = index[0]
            return bess_p[k] + bess_r_p[k] <= p_max

        add_constraint("bess_reg_up_cap", numHours_index, reg_up_cap_func)

        def reg_SoC_cap_func(index):
            k = index[0]
            return bess_l[k + 1] + (self.MESA1_C_p * bess_r_p[k]) * 1000 >= 0

        add_constraint("bess_reg_SoC_cap", numHours_index, reg_SoC_cap_func)

        objective_components = []

        objective_components.append(energy_price * bess_p[RANGE] + reserve_price * bess_r_p[RANGE])

        return constraints, objective_components

    def run_bess_optimization(self, energy_price, reserve_price, p_max, init_soc, final_soc):
        """
        Optimization method for BESS
        :param energy_price:
        :param reserve_price:
        :param p_max:
        :param init_soc:
        :param final_soc:
        :return:
        """
        # build constraints and objective function for TESS
        tess_constraints, tess_objective_components = self.build_bess_constraints(energy_price, reserve_price, p_max,
                                                                             init_soc, final_soc)
        prob = pulp.LpProblem("BESS Optimization", pulp.LpMaximize)
        prob += pulp.lpSum(tess_objective_components), "Objective Function"
        #prob.writeLP("pyversion.lp")
        for c in tess_constraints:
            prob += c
        time_limit = 5
        # TBD: time_limit
        _log.debug("{}".format(prob))
        try:
            prob.solve(pulp.solvers.PULP_CBC_CMD(maxSeconds=time_limit))
        except Exception as e:
            _log.error("PULP failed!")

        _log.debug("Pulp LP Status: {}".format(pulp.LpStatus[prob.status]))
        _log.debug("Pulp LP Objective Value: {}".format(pulp.value(prob.objective)))

        result = {}
        for var in prob.variables():
            result[var.name] = var.varValue
        N = len(energy_price)
        bess_power_inject = [result['bess_p_{}'.format(x)] for x in range(N)]
        bess_power_reserve = [result['bess_r_p_{}'.format(x)] for x in range(N)]
        bess_soc = [result['bess_l_{}'.format(x)] for x in range(N + 1)]
        _log.debug("bess_power_inject: {}".format(bess_power_inject))
        _log.debug("bess_power_reserve: {}".format(bess_power_reserve))
        _log.debug("bess_l: {}".format(bess_soc))
        return bess_power_inject, bess_power_reserve, bess_soc
