import importlib
import logging
from volttron.platform.agent import utils

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

__all__ = ['Model']


class Model(object):
    def __init__(self, config, **kwargs):
        base_module = "volttron.pnnl.models."
        try:
            model_type = config["model_type"]
        except KeyError as e:
            _log.exception("Missing Model Type key: {}".format(e))
            raise e
        _file, model_type = model_type.split(".")
        module = importlib.import_module(base_module + _file)
        model_class = getattr(module, model_type)
        self.model = model_class(config, self)

    def get_q(self, _set, sched_index, market_index, occupied):
        q = self.model.predict(_set, sched_index, market_index, occupied)
        return q
