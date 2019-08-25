#################################
#### MyTransactiveNode with thermal Test
from datetime import timedelta, datetime

from neighbor import Neighbor
from neighbor_model import NeighborModel
from local_asset import LocalAsset
from myTransactiveNode import myTransactiveNode
from vertex import Vertex
from meter_point import MeterPoint
from measurement_type import MeasurementType
from measurement_unit import MeasurementUnit
from temperature_forecast_model import TemperatureForecastModel
from market import Market
from market_state import MarketState
from auction import Auction
from flexible_building import FlexibleBuilding

# create my nTransactive Node which is the auction itself
heat_auction = myTransactiveNode()
mTN = heat_auction
mTN.description = 'heat thermal auction describing the steam distribution loop on WSU campus'
mTN.name = 'steam_loop'
# don't know if I need a meter point?

mTN.meterpoints = []

# instantiate each information service model
# don't think I need any here
mTN.informationServiceModels = []

# instantiate markets and auctions
dayAhead = Auction(energy_type='heat')
auc = dayAhead
auc.name = 'steam_loop'
auc.commitment = False #start without having commited any resources
auc.converged = False
auc.defaultPrice = 0.04 # [$/kWh]
auc.dualityGapThreshold = 0.001 # optimal convergence within 0.1Wh
auc.futureHorizon = timedelta(hours=24)
auc.intervalDuration = timedelta(hours=1)
auc.intervalsToClear = 24
auc.marketClearingTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
auc.marketOrder = 1 # this is the first and only market
auc.nextMarketClearingTime = auc.marketClearingTime + timedelta(hours=1)
auc.initialMarketState = MarketState.Inactive
auc.productionCosts = [] # interval values in [$]
auc.timeIntervals = []
auc.totalDemand = []
auc.totalGeneration = []
auc.totalProductionCost = 0.0
dayAhead = auc

# instantiate loacal assets and their models
# don't think auction has any local assets

auc.localAssets = []

# instantiate neighbors and neighbormodels
# the heat auction has many neighbors
# TUR111 is the SCUE building
TUR111 = Neighbor()
NB = TUR111
NB.lossfactor = 0.01
NB.mechanism = 'consensus'
NB.description = 'substation for SCUE building'
NB.maximumPower = 0
NB.minimumPower = -10000
NB.name = 'TUR111'

TUR111Model = NeighborModel()
NBM = TUR111Model
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = 0.0
NBM.friend = True
NBM.transactive = True
NBM.object = NB
NB.model = NBM
TUR111 = NB
TUR111Model = NBM

# TUR 115 is the chp plant campus interconnect
TUR115 = Neighbor()
NB = TUR115
NB.lossfactor = 0.01
NB.machanism = 'consensus'
NB.description = 'West Campus Thermal Plant Interconnection 1'
NB.minimumPower = 0
NB.maximumPower = 10000
NB.name = 'TUR115'

TUR115Model = NeighborModel()
NBM = TUR115Model
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = 0.0
NBM.defaultPower = 0
NBM.defaultVertices = [Vertex(0.046, 160, 0, True),
                       Vertex(0.048, 160 + 16400 * (0.046 + 0.5 * (0.048 - 0.046)), 16400, True)]
NBM.costParameters = [0, 0, 0]
NBM.friend = True
NBM.transactive = True
NBM.object = NB
NB.model = NBM
TUR115 = NB
TUR115Model = NBM

# SPU125 is CASP interconnect that feeds the west campus chillers
# SPU125 does not interact with the heat auctino

# SPU122 is the ECSS-B interconnect which connects one of the 
# grimes way steam plant generators and the cenral campus inflexible buildings
SPU122 = Neighbor()
NB = SPU122
NB.lossfactor = 0.01
NB.machanism = 'consensus'
NB.description = 'Grimes Way Steam Plant interconnection 1'
NB.minimumPower = -10000
NB.maximumPower = 10000
NB.name = 'SPU122'

SPU122Model = NeighborModel()
NBM = SPU122Model
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = 0.0
NBM.defaultPower = 0
NBM.defaultVertices = [Vertex(0.048, 100, 10, True),
                       Vertex(0.04, 4500, 10000, True)]
NBM.costParameters = [0, 0, 0]
NBM.friend = True
NBM.transactive = True
NBM.object = NB
NB.model = NBM
SPU122 = NB
SPU122Model = NBM

# SPU124 is the second ECSS interconnect which routes power from avista and 
# the second grimes way steam plant generator to east campus buildings
# this node also has the grimes way steam plant boilers

SPU124 = Neighbor()
NB = SPU124
NB.lossfactor = 0.01
NB.machanism = 'consensus'
NB.description = 'East Campus inflexible buildings, one of the GWSP generators, the GWSP boilers, and some chillers'
NB.minimumPower = -10000
NB.maximumPower = 10000
NB.name = 'SPU124'

SPU124Model = NeighborModel()
NBM = SPU124Model
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = 0.0
NBM.defaultPower = 0
NBM.defaultVertices = [Vertex(0.046, -160, -100, True),
                       Vertex(0.048, 1200, 16400, True)]
NBM.costParameters = [0, 0, 0]
NBM.friend = True
NBM.transactive = True
NBM.object = NB
NB.model = NBM
SPU124 = NB
SPU124Model = NBM

# TVW131 and TUR117 do not interface with the steam loop

# create comprehensive list of transactive neighbors to my transactive node
mTN.neighbors = [TUR111, TUR115, SPU122, SPU124]

#############################################################################
## Additional setup script
# the following methods would normally be called soon after the above script
# to launch the system
# 
# call the Market method that will instantiate active future time intervals
dayAhead.check_intervals()

# call the information service that predicts and stores outdoor temps
#PullmanTemperatureForecast.update_information(dayAhead)

# recieve any transactive signals sent to myTransactiveNode from its
# TransactiveNeighbors.
TUR111Model.receive_transactive_signal(heat_auction)
TUR115Model.receive_transactive_signal(heat_auction)
SPU122Model.receive_transactive_signal(heat_auction)
SPU124Model.receive_transactive_signal(heat_auction)

#balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method
dayAhead.balance(heat_auction)

# myTransactiveNode must prepare a set of TransactiveRecords for each of 
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
TUR111Model.prep_transactive_signal(dayAhead, heat_auction)
TUR115Model.prep_transactive_signal(dayAhead, heat_auction)
SPU122Model.prep_transactive_signal(dayAhead, heat_auction)
SPU124Model.prep_transactive_signal(dayAhead, heat_auction)

# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor.
TUR111Model.send_transactive_signal(heat_auction)
TUR115Model.send_transactive_signal(heat_auction)
SPU122Model.send_transactive_signal(heat_auction)
SPU124Model.send_transactive_signal(heat_auction)

# invoke the market object to sum all powers as will be needed by the 
# net supply/demand curve
dayAhead.assign_system_vertices(heat_auction)

# view the system supply/demand curve
dayAhead.view_net_curve(0)
