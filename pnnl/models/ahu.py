import logging
import importlib

from volttron.platform.agent import utils

_log = logging.getLogger(__name__)
utils.setup_logging()

class ahu(object):
    SFS = "sfs"
    MAT = "mat"
    DAT = "dat"
    SAF = "saf"
    OAT = "oat"
    RAT = "rat"

    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        equipment_conf = config.get("equipment_configuration")
        model_conf = config.get("model_configuration")
        self.cpAir = model_conf["cpAir"]
        self.c0 = model_conf["c0"]
        self.c1 = model_conf["c1"]
        self.c2 = model_conf["c2"]
        self.c3 = model_conf["c3"]
        self.power_unit = model_conf.get("unit_power", "kw")
        self.mDotAir = model_conf.get("mDotAir", 0.0)

        self.name = 'AHU'

        self.has_economizer = equipment_conf["has_economizer"]
        self.economizer_limit = equipment_conf["economizer_limit"]
        self.min_oaf = equipment_conf.get("minimum_oaf", 0.15)
        self.vav_flag = equipment_conf.get("variable-volume", True)
        self.sat_setpoint = equipment_conf["supply-air sepoint"]
        self.building_chiller = equipment_conf["building chiller"]
        self.tset_avg = equipment_conf["nominal zone-setpoint"]
        self.tDis = self.sat_setpoint
        self.parent.supply_commodity = "ZoneAirFlow"

        self.fan_power = 0.
        self.mDotAir = 0.
        self.coil_load = 0.

        self.get_input_value = parent.get_input_value
        self.smc_interval = parent.single_market_contol_interval
        self.parent = parent
        self.sfs_name = parent.SFS
        self.mat_name = parent.MAT
        self.dat_name = parent.DAT
        self.saf_name = parent.SAF
        self.oat_name = parent.OAT
        self.rat_name = parent.RAT

        self.sfs = None
        self.mat = None
        self.dat = None
        self.saf = None
        self.oat = None
        self.rat = None

    def update_data(self):
        self.sfs = self.get_input_value(self.sfs_name)
        self.mat = self.get_input_value(self.mat_name)
        self.dat = self.get_input_value(self.dat_name)
        self.saf = self.get_input_value(self.saf_name)
        self.oat = self.get_input_value(self.oat_name)
        self.rat = self.get_input_value(self.rat_name)

    def input_zone_load(self, q_load):
        if self.vav_flag:
            self.mDotAir = q_load
        else:
            self.tDis = q_load
            self.dat = q_load

    def calculate_fan_power(self):
        if self.power_unit == 'W':
            fan_power = (self.c0 + self.c1 * self.mDotAir + self.c2 * pow(self.mDotAir, 2) + self.c3 * pow(self.mDotAir,
                                                                                                           3)) * 1000.  # watts
        else:
            fan_power = self.c0 + self.c1 * self.mDotAir + self.c2 * pow(self.mDotAir, 2) + self.c3 * pow(self.mDotAir,
                                                                                                          3)  # kW
        return fan_power

    def calculate_cooling_load(self, oat):
        if self.has_economizer:
            if oat < self.tDis:
                coil_load = 0.0
            elif oat < self.economizer_limit:
                coil_load = self.mDotAir * self.cpAir * (self.tDis - oat)
            else:
                mat = self.tset_avg * (1.0 - self.min_oaf) + self.min_oaf * oat
                coil_load = self.mDotAir * self.cpAir * (self.tDis - mat)
        else:
            mat = self.tset_avg * (1.0 - self.min_oaf) + self.min_oaf * oat
            coil_load = self.mDotAir * self.cpAir * (self.tDis - mat)

        if coil_load > 0:  # heating mode is not yet supported!
            coil_load = 0.0
        return coil_load

    def calculate_electric_load(self):
        return self.calculate_fan_power()

    def single_market_coil_load(self):
        try:
            coil_load = self.mDotAir * self.cpAir * (self.dat - self.mat)
        except:
            _log.debug("AHU for single market requires dat and mat measurements!")
            coil_load = 0.
        return coil_load

    def calculate_coil_load(self, oat):
        oat = oat if oat is not None else self.oat
        if self.building_chiller and oat is not None:
            if self.smc_interval is not None:
                coil_load = self.single_market_coil_load()
            else:
                coil_load = self.calculate_cooling_load(oat)
        else:
            _log.debug("AHUChiller building does not have chiller or no oat!")
            coil_load = 0.0
        return abs(coil_load)

    def predict(self, set, sched_index, market_index, occupied):
        return None
