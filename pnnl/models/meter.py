import logging
import importlib
import sys
import pandas as pd
from volttron.platform.agent import utils
from datetime import timedelta as td
from volttron.pnnl.models.utils import clamp

_log = logging.getLogger(__name__)
utils.setup_logging()


class Meter(object):
    WBP = "wbp"

    def __init__(self, config, **kwargs):
        model_type = config.get("model_type")
        module = importlib.import_module("volttron.pnnl.models.meter")
        model_class = getattr(module, model_type)
        self.model = model_class(config, self)

    def get_q(self, _set, sched_index, market_index, occupied):
        q = self.model.predict(_set, sched_index, market_index, occupied)
        return q


class simple(object):
    def __init__(self, config, parent, **kwargs):
        self.parent = parent
        self.inputs = parent.inputs

    def update_data(self):
        pass

    def predict(self, _set, sched_index, market_index, occupied):
        pass


