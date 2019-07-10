import logging
import importlib
from volttron.platform.agent import utils
from volttron.pnnl.models.utils import clamp

_log = logging.getLogger(__name__)
utils.setup_logging()


class VAV(object):
    OAT = "oat"
    SFS = "sfs"
    ZT = "zt"
    ZDAT = "zdat"
    ZAF = "zaf"
    CSP = "csp"
    HSP = "hsp"

    def __init__(self, config, **kwargs):
        model_type = config.get("model_type", "firstorderzone")
        module = importlib.import_module("volttron.pnnl.models.vav")
        model_class = getattr(module, model_type)
        self.model = model_class(config, self)

    def get_q(self,  _set, sched_index, market_index, occupied):
        q = self.model.predict(_set, sched_index, market_index, occupied)
        return q


class firstorderzone(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.a1 = config.get("a1", 0)
        self.a2 = config.get("a2", 0)
        self.a3 = config.get("a3", 0)
        self.a4 = config.get("a4", 0)
        type = config.get("terminal_box_type", "VAV")
        self.get_input_value = parent.get_input_value
        self.smc_interval = parent.single_market_contol_interval
        # parent mapping
        # data inputs
        self.oat_name = parent.OAT
        self.sfs_name = parent.SFS
        self.zt_name = parent.ZT
        self.zdat_name = parent.ZDAT
        self.zaf_name = parent.ZAF

        self.oat = self.get_input_value(self.oat_name)
        self.sfs = self.get_input_value(self.sfs_name)
        self.zt = self.get_input_value(self.zt_name)
        # self.zdat = self.get_input_value(self.zdat_name)
        # self.zaf = self.get_input_value(self.zaf_name)

        self.zt_predictions = [self.zt]*parent.market_number
        if type.lower() == "vav":
            self.parent.commodity = "ZoneAirFlow"
            self.predict_quantity = self.getM
        else:
            self.parent.commodity = "DischargeAirTemperature"
            self.predict_quantity = self.getT

    def update_data(self):
        self.oat = self.get_input_value(self.oat_name)
        self.sfs = self.get_input_value(self.sfs_name)
        self.zt = self.get_input_value(self.zt_name)
        # self.zdat = self.get_input_value(self.zdat_name)
        # self.zaf = self.get_input_value(self.zaf_name)
        _log.debug(
            "Update model data: oat: {} - zt: {} - sfs: {}".format(self.oat, self.zt, self.sfs))

    def update(self, _set, sched_index, market_index):
        self.zt_predictions[market_index] = _set

    def predict(self, _set, sched_index, market_index, occupied):
        if self.smc_interval is not None or market_index == -1:
            oat = self.oat
            zt = self.zt
            occupied = self.sfs if self.sfs is not None else occupied
            sched_index = self.parent.current_datetime.hour
        else:
            zt = self.zt_predictions[market_index]
            oat = self.parent.oat_predictions[market_index] if self.parent.oat_predictions else self.oat
        q = self.predict_quantity(oat, zt, _set, sched_index)
        _log.debug("{}: VAV_MODEL predicted {} - zt: {} - set: {} - sched: {}".format(self.parent.agent_name, q, zt, _set, sched_index))
        # might need to revisit this when doing both heating and cooling
        if occupied:
            q = clamp(q, min(self.parent.flexibility), max(self.parent.flexibility))
        else:
            q = 0.0
        return q

    def getT(self, oat, temp, temp_stpt, index):
        T = temp_stpt*self.a1[index]+temp*self.a2[index]+oat*self.a3[index]+self.a4[index]
        return T

    def getM(self, oat, temp, temp_stpt, index):
        M = temp_stpt*self.a1[index]+temp*self.a2[index]+oat*self.a3[index]+self.a4[index]
        return M
