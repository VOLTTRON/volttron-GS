import itertools
import numpy as np
import pandas
import pulp
import logging
import importlib
import variable_group
from variable_group import VariableGroup, RANGE
from volttron.platform.agent import utils


class TESS(object):

    def __init__(self, config, **kwargs):
        model_type = config.get("model_type", "tess")
        module = importlib.import_module("volttron.pnnl.models.tess")
        model_class = getattr(module, model_type)
        self.model = model_class(config, self)


class tess(object):
    def __init__(self, config, parent, **kwargs):
        self.a_coef = config.get("a_coef", [0.257986, 0.0389016, -0.00021708, 0.0468684, -0.00094284, -0.00034344])
        self.b_coef = config.get("b_coef", [0.933884, -0.058212, 0.00450036, 0.00243, 0.000486, -0.001215])
        self.p_coef = np.array(config.get("p_coef", [4.0033, -3.5162, -5.4302, 5.6807, -1.1989, -0.1963, 0.8593]))
        self.r_coef = np.array(config.get("r_coef", [0.9804, -2.6207, 3.6708, -2.6975, 0.0446, 1.2533, 0.2494]))
        self.c_coef = np.array(config.get("c_coef", [0.222903, 0.313387, 0.46371]))
        self.Q_norm = config.get("Q_norm", 95)  # kW
        self.Q_stor = config.get("Q_stor", 500)  # kWh
        self.COP = config.get("COP", 3.5)
        self.Cf = config.get("Cf", 3.915)  # kJ/kg-K
        self.m_ice = config.get("m_ice", 5.24)  # kg/s
        self.T_cw_ch = config.get("T_cw_ch", -5)  # degrees C
        self.T_cw_norm = config.get("T_cw_norm", 4.4)  # degrees C
        self.T_fr = config.get("T_fr", 0)  # degrees C

    @staticmethod
    def poly(c, x):
        """

        :param c: Array of Float64
        :param x:
        :return:
        """
        result = None
        if isinstance(c, np.ndarray):
            arr = np.array(range(1, len(c)))
            result = c[0] + np.sum(c[1:] * (x ** arr))
        return result

    def sigma_12(self, T_cw, t_out, coef):
        """

        :param T_cw:
        :param t_out:
        :param coef: Array of Float64
        :return:
        """
        result = coef[0] + coef[1] * T_cw + coef[2] * T_cw ** 2 + coef[3] * t_out + coef[4] * t_out ** 2 + coef[
            5] * T_cw * t_out
        return result

    def sigma_3(self, PLR):
        return self.poly(self.c_coef, PLR)

    def Q_avail(self, T_cw, t_out):
        return self.Q_norm * self.sigma_12(T_cw, t_out, self.a_coef)

    def P_chiller(self, q_chiller, T_cw, t_out):
        """

        :param q_chiller: Cooling load
        :param T_cw: Chilled water temperature
        :param t_out: Outdoor temperature
        :return:
        """
        return self.Q_avail(T_cw, t_out) * self.sigma_12(T_cw, t_out, self.b_coef) * self.sigma_3(q_chiller / self.Q_avail(T_cw, t_out))

    def u_UB(self, l):
        return self.poly(self.p_coef, l) * self.m_ice * self.Cf * (self.T_fr - self.T_cw_ch)

    def u_LB(self, l):
        return self.poly(self.r_coef, l) * self.m_ice * self.Cf * (self.T_cw_norm - self.T_fr)

    def constant(self, x):
        def _constant(*args, **kwargs):
            return x

        return _constant

    def build_tess_constraints(self, energy_price, reserve_price, t_out, q_cool, init_soc, final_soc):
        """
        Build constraints and objective function for TESS
        :param energy_price: Energy price from city market
        :param reserve_price: Reserve price from city market
        :param t_out: Outdoor temperature -- degree celcius
        :param q_cool: Cooling load --- kW
        :param init_soc: initial SOC
        :param final_soc: final SOC
        :return:
        """
        numHours = len(energy_price)
        #print("{}, {}, {}, {}".format(numHours, len(reserve_price), len(t_out), len(q_cool)))
        if numHours != len(reserve_price) or numHours != len(t_out) or numHours != len(q_cool):
            raise (TypeError("The lengths of energy_price, reserve_price, and q_cool should match."))

        print("EnergyPrice: {}".format(energy_price))
        print("ReservePrice: {}".format(reserve_price))
        print("T_out: {}".format(t_out))
        print("Q_cool: {}".format(q_cool))

        numHours_range = (range(numHours),)
        n2_range = (range(numHours + 1), )
        tess_p = VariableGroup("tess_p", indexes=numHours_range, lower_bound_func=self.constant(0.0)) # Power withdrawal from the grid (non-negative), unit: kW
        tess_l = VariableGroup("tess_l", indexes=n2_range, lower_bound_func=self.constant(0.1), upper_bound_func=self.constant(0.9)) # State of charge (SoC) in [0.1, 0.9]
        tess_r = VariableGroup("tess_r", indexes=numHours_range, lower_bound_func=self.constant(0.0)) # Reserve power (non-negative)
        tess_u = VariableGroup("tess_u", indexes=numHours_range) # Ice-storage charging rate
        tess_u_p = VariableGroup("tess_u_p", indexes=numHours_range, lower_bound_func=self.constant(0.0), base_name="u^+") # Positive parts of ice-storage charging rate
        tess_u_n = VariableGroup("tess_u_n", indexes=numHours_range, upper_bound_func=self.constant(0.0), base_name="u^-") # Negative parts of ce-storage charging rate
        tess_b = VariableGroup("tess_b", indexes=numHours_range, is_binary_var=True, ) # Ice-storage charging/discharging indicator: 1 == Charging, 0 == Discharging
        tess_u_r = VariableGroup("tess_u_r", indexes=numHours_range, base_name="\\tilde{u}") # Ice-storage charging rate
        tess_u_p_r = VariableGroup("tess_u_p_r", indexes=numHours_range, lower_bound_func=self.constant(0.0), base_name="\\tilde{u}^+") # Positive parts of ice-storage charging rate
        tess_u_n_r = VariableGroup("tess_u_n_r", indexes=numHours_range, upper_bound_func=self.constant(0.0), base_name="\\tilde{u}^-") # Negative parts of ce-storage charging rate
        tess_b_r = VariableGroup("tess_b_r", indexes=numHours_range, is_binary_var=True, base_name="\\tilde{b}") # Ice-storage charging/discharging indicator: 1 == Charging, 0 == Discharging

        t_UB = np.array([0.1, 0.6, 0.78, 0.9])
        t_UB_range = range(len(t_UB)-1)
        u_UB_res = np.array([self.u_UB(x) for x in t_UB[0:]])
        #print("u_UB_res: {}".format(u_UB_res))
        #print("t_UB: {}".format(t_UB[0:-1] - t_UB[1:]))
        a_UB = (u_UB_res[0:-1] - u_UB_res[1:]) / (t_UB[0:-1] - t_UB[1:])
        b_UB = u_UB_res[0:-1] - a_UB * t_UB[0:-1]

        print("a_UB: {}".format(a_UB))
        print("b_UB: {}".format(b_UB))

        tess_l_UB = VariableGroup("tess_l_UB", (t_UB_range, range(numHours),), base_name="\\overline{l}") # Piecewise linearization weights for u_UB
        tess_S_UB = VariableGroup("tess_S_UB", (t_UB_range, range(numHours),), is_binary_var=True, base_name="\\overline{S}") # Piecewise linearization weights for u_UB

        t_LB = np.array([0.1, 0.3, 0.5, 0.65, 0.78, 0.9])
        t_LB_range = range(len(t_LB)-1)

        u_LB_res = np.array([self.u_LB(x) for x in t_LB[0:]])
        #print("Len of u_LB_res: {}, len of t_LB: {}".format(len(u_LB_res), len(t_LB)))
        #print("u_LB_res: {}, t_LB: {}".format(u_LB_res[0:-1], u_LB_res[1:]))
        #print("u_LB_res: {}, t_LB: {}".format(t_LB[0:-1], t_LB[1:]))

        a_LB = (u_LB_res[0:-1] - u_LB_res[1:]) / (t_LB[0:-1] - t_LB[1:])
        b_LB = u_LB_res[0:-1] - a_LB * t_LB[0:-1]
        print("a_LB: {}".format(a_LB))
        print("b_LB: {}".format(b_LB))

        tess_l_LB = VariableGroup("tess_l_LB", (t_LB_range, range(numHours),), base_name="\\underline{\\tilde{l}}") # Piecewise linearization weights for u_LB
        tess_S_LB = VariableGroup("tess_S_LB", (t_LB_range, range(numHours),), is_binary_var=True, base_name="\\underline{\\tilde{S}}")# Piecewise linearization weights for u_LB

        t_PLR = np.array([0, 0.5, 1])
        a_Pch_p = np.zeros((len(t_PLR)-1, numHours))
        for k in range(numHours):
            a = np.array([self.P_chiller(x * self.Q_avail(self.T_cw_ch, t_out[k]), self.T_cw_ch, t_out[k]) for x in t_PLR[0:-1]])
            b = np.array([self.P_chiller(x * self.Q_avail(self.T_cw_ch, t_out[k]), self.T_cw_ch, t_out[k]) for x in t_PLR[1:]])
            a_Pch_p[:, k] = (a - b)/(t_PLR[0:-1] - t_PLR[1:])/self.Q_avail(self.T_cw_ch, t_out[k])

        b_Pch_p = np.zeros((len(t_PLR)-1, numHours))
        for k in range(numHours):
            a = np.array([self.P_chiller(x * self.Q_avail(self.T_cw_ch, t_out[k]), self.T_cw_ch, t_out[k]) for x in t_PLR[0:-1]])
            s = [x * self.Q_avail(self.T_cw_ch, t_out[k]) for x in t_PLR[0:-1]]
            b = a_Pch_p[:, k] * s
            #b_Pch_p[:, k] = self.P_chiller.(t_PLR[1:end - 1] * self.Q_avail(self.T_cw_ch, T_out[k]), self.T_cw_ch, T_out[k]) - a_Pch_p[:,k]. * t_PLR[1:end - 1] * self.Q_avail(self.T_cw_ch, T_out[k]);
            b_Pch_p[:, k] = a - b

        a_Pch_n = np.zeros((len(t_PLR)-1, numHours))
        for k in range(numHours):
            a = np.array([self.P_chiller(x * self.Q_avail(self.T_cw_norm, t_out[k]), self.T_cw_norm, t_out[k]) for x in t_PLR[0:-1]])
            b = np.array([self.P_chiller(x * self.Q_avail(self.T_cw_norm, t_out[k]), self.T_cw_norm, t_out[k]) for x in t_PLR[1:]])
            a_Pch_n[:, k] = (a - b) / (t_PLR[0:-1] - t_PLR[1:]) / self.Q_avail(self.T_cw_norm, t_out[k])

        b_Pch_n = np.zeros((len(t_PLR)-1, numHours))
        for k in range(numHours):
            a = np.array([self.P_chiller(x * self.Q_avail(self.T_cw_norm, t_out[k]), self.T_cw_norm, t_out[k]) for x in t_PLR[0:-1]])
            s = [x * self.Q_avail(self.T_cw_norm, t_out[k]) for x in t_PLR[0:-1]]
            b = a_Pch_n[:, k] * s
            b_Pch_n[:, k] = a - b

        #print("a_Pch_p: {}".format(a_Pch_p))
        #print("b_Pch_p: {}".format(b_Pch_p))
        #print("a_Pch_n: {}".format(a_Pch_n))
        #print("b_Pch_n: {}".format(b_Pch_n))

        t_PLR_range = range(len(t_PLR)-1)
        tess_q_p = VariableGroup("tess_q_p", (t_PLR_range, range(numHours),), base_name="q^+")
        tess_S_p = VariableGroup("tess_S_p", (t_PLR_range, range(numHours),), is_binary_var=True, base_name="S^+")  # Piecewise binary variable for q_p
        tess_q_n = VariableGroup("tess_q_n", (t_PLR_range, range(numHours),), base_name="q^-")
        tess_S_n = VariableGroup("tess_S_n", (t_PLR_range, range(numHours),), is_binary_var=True, base_name="S^-")  # Piecewise binary variable for q_n
        tess_q_p_r = VariableGroup("tess_q_p_r", (t_PLR_range, range(numHours),), base_name="\\tilde{q}^+")
        tess_S_p_r = VariableGroup("tess_S_p_r", (t_PLR_range, range(numHours),), is_binary_var=True, base_name="\\tilde{S}^+")  # Piecewise binary variable for q_p_r
        tess_q_n_r = VariableGroup("tess_q_n_r", (t_PLR_range, range(numHours),), base_name="\\tilde{q}^-")
        tess_S_n_r = VariableGroup("tess_S_n_r", (t_PLR_range, range(numHours),), is_binary_var=True, base_name="\\tilde{S}^-")  # Piecewise binary variable for q_n_r

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

        name = 'tess_conInitSoc_0'
        checkInitSoC = tess_l[0] == init_soc
        constraints.append((checkInitSoC, name))

        if final_soc >= 0:
            name = 'tess_conFinalSoc_0'
            checkFinalSoC = tess_l[numHours] == final_soc
            constraints.append((checkFinalSoC, name))

        numHours_index = (range(numHours),)
        def tess_conSoDynamics_func(index):
            k = index[0]
            return tess_l[k+1] - tess_l[k] == tess_u[k] / self.Q_stor
        add_constraint("tess_conSoDynamics", numHours_index, tess_conSoDynamics_func)

        def tess_conThermalCharging_func(index):
            k = index[0]
            return tess_u[k] == tess_u_p[k] + tess_u_n[k]
        add_constraint("tess_conThermalCharging", numHours_index, tess_conThermalCharging_func)

        def tess_ab_func(index):
            k = index[0]
            return tess_l[k] == pulp.lpSum(tess_l_UB[RANGE,k])
        add_constraint("tess_ab", numHours_index, tess_ab_func)

        def tess_ab1_func(index):
            k = index[0]
            return pulp.lpSum(tess_S_UB[RANGE, k]) == 1

        add_constraint("tess_ab1", numHours_index, tess_ab1_func)

        t_UB_index = (range(len(t_UB)-1), range(numHours),)

        def tess_ab2_func(index):
            i, k = index
            return tess_S_UB[i, k] * t_UB[i] <= tess_l_UB[i, k]
        add_constraint("tess_ab2", t_UB_index,tess_ab2_func)

        def tess_ab3_func(index):
            i, k = index
            return tess_l_UB[i, k] <= tess_S_UB[i, k] * t_UB[i+1]
        add_constraint("tess_ab3", t_UB_index, tess_ab3_func)

        def tess_conThermalChargingUB(index):
            k = index[0]
            return tess_u_p[k] <= pulp.lpSum(a_UB * tess_l_UB[RANGE, k] + b_UB * tess_S_UB[RANGE, k])

        add_constraint("tess_conThermalChargingUB", numHours_index, tess_conThermalChargingUB) # u_UB(l[k])

        def tess_ab6_func(index):
            k = index[0]
            return tess_u_p[k] <= tess_b[k] * 1e10

        add_constraint("tess_ab6", numHours_index, tess_ab6_func)  # u_UB(l[k])

        def tess_ab5_func(index):
            k = index[0]
            return tess_l[k] == pulp.lpSum(tess_l_LB[RANGE, k])

        add_constraint("tess_ab5", numHours_index, tess_ab5_func)  # u_UB(l[k])

        def tess_ab7_func(index):
            k = index[0]
            return pulp.lpSum(tess_S_LB[RANGE, k]) == 1

        add_constraint("tess_ab7", numHours_index, tess_ab7_func)

        t_LB_index = (range(len(t_LB)-1), range(numHours),)
        def tess_ab8_func(index):
            i, k = index
            return tess_S_LB[i, k] * t_LB[i] <= tess_l_LB[i, k]
        add_constraint("tess_ab8", t_LB_index, tess_ab8_func)

        def tess_ab9_func(index):
           i, k = index
           return tess_l_LB[i, k] <= tess_S_LB[i, k] * t_LB[i + 1]

        add_constraint("tess_ab9", t_LB_index, tess_ab9_func)

        def tess_conThermalChargingLB_func(index):
            k = index[0]
            print("unr: {}".format(-pulp.lpSum(a_LB * tess_l_LB[RANGE, k] + b_LB * tess_S_LB[RANGE, k])))
            return tess_u_n[k] >= -pulp.lpSum(a_LB * tess_l_LB[RANGE, k] + b_LB * tess_S_LB[RANGE, k])

        add_constraint("tess_conThermalChargingLB", numHours_index, tess_conThermalChargingLB_func) # -u_LB(l[k])

        def tess_bc1_func(index):
            k = index[0]
            return tess_u_n[k] >= -(1 - tess_b[k]) * 1e10

        add_constraint("tess_bc1", numHours_index, tess_bc1_func)

        def tess_bc2_func(index):
            k = index[0]
            return tess_u[k] + q_cool[k] >= 0

        add_constraint("tess_bc2", numHours_index, tess_bc2_func)

        def tess_bc3_func(index):
            k = index[0]
            return q_cool[k] + tess_u_p[k] == pulp.lpSum(tess_q_p[RANGE, k])

        add_constraint("tess_bc3", numHours_index, tess_bc3_func)

        def tess_bc4_func(index):
            k = index[0]
            return pulp.lpSum(tess_S_p[RANGE, k]) == 1

        add_constraint("tess_bc4", numHours_index, tess_bc4_func)

        t_PLR_index = (range(len(t_PLR)-1), range(numHours))

        def tess_S_p_func(index):
            i, k = index
            return tess_S_p[i, k] * t_PLR[i] * self.Q_avail(self.T_cw_ch, t_out[k]) <= tess_q_p[i, k]

        add_constraint("tess_S_p_constr", t_PLR_index, tess_S_p_func)

        def tess_D_p_func(index):
            i, k = index
            return tess_q_p[i, k] <= tess_S_p[i, k] * t_PLR[i + 1] * self.Q_avail(self.T_cw_ch, t_out[k])

        add_constraint("tess_D_p", t_PLR_index, tess_D_p_func)

        def tess_q_cool_func(index):
            k = index[0]
            return q_cool[k] + tess_u_n[k] == pulp.lpSum(tess_q_n[RANGE, k])

        add_constraint("tess_q_cool", numHours_index, tess_q_cool_func)

        def tess_S_n_func(index):
            k = index[0]
            return pulp.lpSum(tess_S_n[RANGE, k]) == 1

        add_constraint("tess_S_n_constr", numHours_index, tess_S_n_func)

        def tess_X_n_func(index):
            i, k = index
            return tess_S_n[i, k] * t_PLR[i] * self.Q_avail(self.T_cw_norm, t_out[k]) <= tess_q_n[i, k]

        add_constraint("tess_X_n", t_PLR_index, tess_X_n_func)

        def tess_q_n_func(index):
            i, k = index
            return tess_q_n[i, k] <= tess_S_n[i, k] * t_PLR[i + 1] * self.Q_avail(self.T_cw_norm, t_out[k])

        add_constraint("tess_S_n_constr", t_PLR_index, tess_q_n_func)

        def tess_conPowConsumption_func(index):
            k = index[0]

            chill = self.P_chiller(q_cool[k], self.T_cw_ch, t_out[k])
            xx = (1 - tess_b[k]) * chill
            yy = tess_b[k] * self.P_chiller(q_cool[k], self.T_cw_norm, t_out[k])
            a = a_Pch_p[:, k] * tess_q_p[RANGE, k]
            b = b_Pch_p[:, k] * tess_S_p[RANGE, k]
            c = a_Pch_n[:, k] * tess_q_n[RANGE,k]
            d = b_Pch_n[:, k] * tess_S_n[RANGE,k]
            return tess_p[k] == pulp.lpSum(a+b) + pulp.lpSum(c+d) - xx - yy

        add_constraint("tess_conPowConsumption", numHours_index, tess_conPowConsumption_func)

        def tess_conReserveThermalCharging_func(index):
            k = index[0]
            return tess_u_r[k] == tess_u_p_r[k] + tess_u_n_r[k]

        add_constraint("tess_conReserveThermalCharging", numHours_index, tess_conReserveThermalCharging_func)

        def tess_conReserveThermalChargingUB(index):
            k = index[0]
            return tess_u_p_r[k] <= tess_u_p[k]

        add_constraint("conReserveThermalChargingUB", numHours_index, tess_conReserveThermalChargingUB)

        def tess_conReserveThermalCharginge10_func(index):
            k = index[0]
            return tess_u_p_r[k] <= tess_b_r[k] * 1e10

        add_constraint("tess_conReserveThermalCharginge10", numHours_index, tess_conReserveThermalCharginge10_func)

        def tess_conReserveThermalChargingLB(index):
            k = index[0]
            return tess_u_n_r[k] >= -pulp.lpSum(a_LB * tess_l_LB[RANGE, k] + b_LB * tess_S_LB[RANGE, k])
        add_constraint("tess_conReserveThermalChargingLB", numHours_index, tess_conReserveThermalChargingLB) # u_LB(l[k])

        def tess_conReserveThermalChargingLBe10_func(index):
            k = index[0]
            return tess_u_n_r[k] >= (1 - tess_b_r[k]) * -1e10

        add_constraint("tess_conReserveThermalChargingLBe10", numHours_index, tess_conReserveThermalChargingLBe10_func)

        def tess_ab10_func(index):
            k = index[0]
            return tess_u_r[k] + q_cool[k] >= 0

        add_constraint("tess_ab10", numHours_index, tess_ab10_func)

        def tess_ab11_func(index):
            k = index[0]
            return q_cool[k] + tess_u_p_r[k] == pulp.lpSum(tess_q_p_r[RANGE, k])

        add_constraint("tess_ab11", numHours_index, tess_ab11_func)

        def tess_ab12_func(index):
            k = index[0]
            return pulp.lpSum(tess_S_p_r[RANGE, k]) == 1

        add_constraint("tess_ab12", numHours_index, tess_ab12_func)

        def tess_ab13_func(index):
            i, k = index
            return tess_S_p_r[i, k] * t_PLR[i] * self.Q_avail(self.T_cw_ch, t_out[k]) <= tess_q_p_r[i, k]

        add_constraint("tess_ab13", t_PLR_index, tess_ab13_func)

        def tess_ab14_func(index):
            i, k = index
            return tess_q_p_r[i, k] <= tess_S_p_r[i, k] * t_PLR[i + 1] * self.Q_avail(self.T_cw_ch, t_out[k])

        add_constraint("ab14", t_PLR_index, tess_ab14_func)

        def tess_ab15_func(index):
            k = index[0]
            return q_cool[k] + tess_u_n_r[k] == pulp.lpSum(tess_q_n_r[RANGE, k])

        add_constraint("tess_ab15", numHours_index, tess_ab15_func)

        def tess_ab16_func(index):
            k = index[0]
            return pulp.lpSum(tess_S_n_r[RANGE, k]) == 1

        add_constraint("tess_ab16", numHours_index, tess_ab16_func)

        def tess_snr_func(index):
            i, k = index
            return tess_S_n_r[i, k] * t_PLR[i] * self.Q_avail(self.T_cw_norm, t_out[k]) <= tess_q_n_r[i, k]

        add_constraint("tess_snr", t_PLR_index, tess_snr_func)

        def tess_qnr_func(index):
            i, k = index
            return tess_q_n_r[i, k] <= tess_S_n_r[i, k] * t_PLR[i + 1] * self.Q_avail(self.T_cw_norm, t_out[k])

        add_constraint("tess_qnr", t_PLR_index, tess_qnr_func)

        def tess_conReserveCapacity(index):
            k = index[0]

            xx = (1 - tess_b_r[k]) * self.P_chiller(q_cool[k], self.T_cw_ch, t_out[k])
            yy = tess_b_r[k] * self.P_chiller(q_cool[k], self.T_cw_norm, t_out[k])
            a = a_Pch_p[:, k] * tess_q_p_r[RANGE, k]
            b = b_Pch_p[:, k] * tess_S_p_r[RANGE, k]
            c = a_Pch_n[:, k] * tess_q_n_r[RANGE, k]
            d = b_Pch_n[:, k] * tess_S_n_r[RANGE, k]
            return tess_r[k] == tess_p[k] - pulp.lpSum(a+b)\
                   - pulp.lpSum(c+d)\
                   + xx\
                   + yy

        add_constraint("tess_conReserveCapacity", numHours_index, tess_conReserveCapacity)

        def tess_conReserveEnergyLimit_func(index):
            k = index[0]
            print("Qstor: {}".format(tess_l[k] + tess_u_r[k] / self.Q_stor))
            return tess_l[k] + tess_u_r[k] / self.Q_stor >= 0

        add_constraint("tess_conReserveEnergyLimit", numHours_index, tess_conReserveEnergyLimit_func)
        objective_components = list()

        objective_components.append((-energy_price * tess_p[RANGE])/1000 + (reserve_price * tess_r[RANGE])/ 1000)
        return constraints, objective_components

    def run_tess_optimization(self, energy_price, reserve_price, t_out, q_cool, init_soc, final_soc):
        """

        :param energy_price:
        :param reserve_price:
        :param t_out:
        :param q_cool:
        :param init_soc:
        :param final_soc:
        :return:
        """
        # build constraints and objective function for TESS
        tess_constraints, tess_objective_components = self.build_tess_constraints(energy_price,
                                                                                  reserve_price,
                                                                                  t_out,
                                                                                  q_cool,
                                                                                  init_soc,
                                                                                  final_soc)

        prob = pulp.LpProblem("TESS_BESS Optimization", pulp.LpMaximize)
        prob += pulp.lpSum(tess_objective_components), "Objective Function"
        prob.writeLP("pyversion.lp")
        for c in tess_constraints:
            prob += c
        prob.writeLP("tess_output.txt")
        time_limit = 30
        # TBD: time_limit
        try:
            prob.solve(pulp.solvers.PULP_CBC_CMD(maxSeconds=time_limit))
        except Exception as e:
            print("PULP failed!")

        print(pulp.LpStatus[prob.status])
        print(pulp.value(prob.objective))

        result = {}
        for var in prob.variables():
            result[var.name] = var.varValue

        N=len(energy_price)
        p_result = [result['tess_p_{}'.format(x)] for x in range(N) ]
        r_result = [result['tess_r_{}'.format(x)] for x in range(N)]

        tess_powerInject = - np.array(p_result) / 1000  # MW
        tess_powerReserve = np.array(r_result) / 1000  # MW

        tess_soc = result['tess_l']
        return tess_powerInject, tess_powerReserve, tess_soc

