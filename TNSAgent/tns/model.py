
from vertex import Vertex
#from time_interval import TimeInterval
from local_asset import LocalAsset
from interval_value import IntervalValue

import logging
#utils.setup_logging()
_log = logging.getLogger(__name__)


class Model:
    def __init__(self):
        """Top-level class for all transactive model classes"""
        # ACTIVE VERTICES
        # An array of vertices that represent the production of a resource
        # (or consumption of load) as a function of marginal price.
        self.activeVertices = []  # IntervalValue

        #         COST PARAMETERS
        #         Three coefficients [a(1),a(2),a(3)] that may be used to calculate
        #         production cost of resources (or gross consumer surplus (i.e.,
        #         utility) for loads?).
        #                   cost = a(3)*p^2 + a(2)*p + a(1) [$/h]
        self.costParameters = [0.0, 0.0, 0.0]  # {mustBeReal}

        #         #DEFAULT VERTICES
        #         #Array of vertices that may be used to initialize price behaviors.
        #         #(See struct Vertex.)
        self.defaultVertices = [[Vertex(float("inf"), 0.0, 1)]]

        # DUAL COSTS
        # Array of dual costs for each active time interval. For a neighbor,
        # the dual cost is equal to production surplus (aka "profit"), plus
        # other Lagrangian and constraint terms during the importation of
        # electricity. During the exportation of electricity, dual costs
        # include the (net) consumer surplus, plus other Lagrangian terms.
        # [$]
        self.dualCosts = []  # IntervalValue

        # METERPOINTS
        # Array of meter points called upon by this model. [See class MeterPoint.]
        self.meterPoints = []  # MeterPoint

        # NAME
        # Name of this neighbor. By convention, use the same name as is
        # applied to the object.
        self.name = ''  # char

        # OBJECT
        # Cross reference from this model to the corresponding neighbor
        # object.
        self.object = None  # object Neighbor

        # PRODUCTION COSTS
        # Array of production costs for active time intervals. For a
        # neighbor, production costs apply only during the importation of
        # electricity. [$]
        self.productionCosts = []  # IntervalValue[]

        # RESERVE MARGIN
        # Array of margins between maximum and scheduled powers in active
        # time intervals. An estimate of spinning reserve is tracked. The
        # long-term goal is to solve for a target reserve margin, but doing
        # so requires having multiple resource that may be engaged or
        # disengaged, spinning or non-spinning. [avg.kW]
        self.reserveMargins = []  # IntervalValue[]

        # SCHEDULED POWERS
        # Array of scheduled real power for this resource in each of the
        # active time intervals. Values should be positive for imported
        # power negative for exported. [avg. kW]
        self.scheduledPowers = []  # IntervalValue

        # TOTAL DUAL COST
        # Sum of dual costs for the entire set of future time horizon
        # intervals. [$]
        self.totalDualCost = 0.0  # real


        # TOTAL PRODUCTION COST
        # Sum of production costs for the entire set of future time horizon
        # intervals. This should not include gross consumer surplus during
        # exportation of electricity to the neighbhor. [$]
        self.totalProductionCost = 0.0  # {mustBeReal, mustBeNonnegative}

    ## schedule() - have object schedule its power in active time intervals
    def schedule(self, mkt):
        pass
        # If the object is a NeighborModel give its vertices priority
        # if isinstance(obj, NeighborModel):
        #     self.update_vertices(mkt)
        #     self.schedule_power(mkt)
        #
        # # But give power scheduling priority for a LocalAssetModel
        # elif isinstance(obj, LocalAssetModel):
        #     self.schedule_power(mkt)
        #     self.schedule_engagement(mkt)  # only LocalAssetModels
        #     self.update_vertices(mkt)
        #
        # else:
        #     _log.warning('obj needs to be either NeighborModel or LocalAssetModel')
        #     return
        #
        # # Have the objects estimate their available reserve margin
        # self.calculate_reserve_margin(mkt)

    ## update_costs() - have model object update and store its costs
    ## SEALED - DONOT MODIFY
    def update_costs(self, mkt):

        # Initialize sums of production and dual costs
        self.totalProductionCost = 0.0
        self.totalDualCost = 0.0

        # Have object update and store its production and dia costs in
        # each active time interval
        self.update_production_costs(mkt)
        self.update_dual_costs(mkt)

        # Sum total production and dual costs through all time intervals
        if isinstance(self.productionCosts[0], list):
            self.totalProductionCost = 0.0
            self.totalDualCost = 0.0
            for pc in self.productionCosts:
                self.totalProductionCost = self.totalProductionCost + sum([x.value for x in pc])
            for dc in self.dualCosts:
                self.totalDualCost = self.totalDualCost + sum([x.value for x in dc])
        else:
            self.totalProductionCost = sum([x.value for x in self.productionCosts])
            self.totalDualCost = sum([x.value for x in self.dualCosts])

    ## Abstract AbstractModel methods
    # These abstract methods must be redefined (made concrete) by NeighborModel
    # and LocalAssetModel subclasses. (This requirement is met by simply doing
    # so in the LocalAssetModel and NeighborModel base classes.)
    def calculate_reserve_margin(self, mkt):
        pass

    def schedule_power(self, mkt):
        pass

    def update_dual_costs(self, mkt):
        pass

    def update_production_costs(self, mkt):
        pass

    def update_vertices(self, mkt):
        pass

    def schedule_engagement(self, mkt):
        pass


if __name__ == '__main__':
    pass
