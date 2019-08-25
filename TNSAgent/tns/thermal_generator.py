# Thermal generators are local assets which produce power
# They consume fuel (cost) and produce electricity and possibly heat

from local_asset import LocalAsset

class ThermalGenerator(LocalAsset, object):
    # This is a dispatchable resource
    # CHP capabilities will be optional in the future
    def __init__(self):
        super(ThermalGenerator, self).__init__()
