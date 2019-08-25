from neighbor import Neighbor

class Thermal_Agent(Neighbor):
    # thermal agent class
    # thermal agents are children of the neighbor base class
    # they are remote entities with which nodes interact
    # they are also members of the transactive network and are
    # obligated to negotiate via transactive signals
    
    def __init__(self):
        # Required thermal agent properties
        # these properties are required by superclass Neighbor
        # and its parents:
        #         description = ''
        #         maximumPower = 0.0        # "hard" power constraint [signed avg.kW]
        #         meterPoints = MeterPoint.empty               # see class MeterPoint
        #         minimumPower = 0.0      # a "hard" power constraint [signed avg.kW]
        #         model = NeighborModel.empty # a cross-reference to associated model
        #         name = ''
        #         subclass = ''                       # the object's class membership
        #         status = 'unknown'
        #         lossFactor = 0.01 # [dimensionless, 0.01 = 1 # loss]
        #         mechanism = 'consensus'

        self.energy_type = 'heat'
        