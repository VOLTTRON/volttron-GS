#################################
#### MyTransactiveNode with thermal Test
from datetime import timedelta, datetime

from neighbor import Neighbor
from neighbor_model import NeighborModel
from local_asset import LocalAsset
from myTransactiveNode import myTransactiveNode
from meter_point import MeterPoint
from measurement_type import MeasurementType
from measurement_unit import MeasurementUnit
from temperature_forecast_model import TemperatureForecastModel
from market import Market
from market_state import MarketState
from auction import Auction
from flexible_building import FlexibleBuilding
from vertex import Vertex
from helpers import prod_cost_from_vertices
from interval_value import IntervalValue

# create a neighbor model
TUR111 = myTransactiveNode()
mTN = TUR111
mTN.description = 'substation TUR111 includes SCUE building and and connection with AVISTA'
mTN.name = 'T111'

#set up AVISTA power meter
SCUE_meter = MeterPoint()
MP = SCUE_meter
MP.description = 'meters SCUE building electric use from AVISTA'
MP.measurementType = MeasurementType.PowerReal
MP.measurement = MeasurementUnit.kWh
SCUE_meter = MP

# provide a cell array of all the MeterPoints to myTransactiveNode
mTN.meterpoints = [SCUE_meter]

## instantiate each Information Service Model
# this is a service that can be queried for information
# includes model prediction for future time intervals
# Pullman Temperature Forecast <-- Information service model
PullmanTemperatureForecast = TemperatureForecastModel()
ISM = PullmanTemperatureForecast
ISM.name = 'PullmanTemperatureForecast'
ISM.predictedValues = [] # dynamically assigned

mTN.informationServiceModels = [PullmanTemperatureForecast]

########################################################################################################
## Instantiate Markets and Auctions
# Markets specify active TimeIntervals
# Auctions handle thermal loads

## Day Ahead Market
dayAhead = Market(measurementType = [MeasurementType.PowerReal, MeasurementType.Heat, MeasurementType.Cooling])
MKT = dayAhead
MKT.name = 'T111_Market'
MKT.commitment = False # start without having commited any resources
MKT.converged = False # start without having converged
MKT.defaultPrice = [0.03, 0.01, 0.02] # [$/kWh]
MKT.dualityGapThreshold = 0.001 #optimal convergence within 0.1Wh
MKT.futureHorizon = timedelta(hours=24)
MKT.intervalDuration = timedelta(hours=1)
MKT.intervalsToClear = 24 # clear entire horizon at once, this is a default value
MKT.marketClearingTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) # align with top of hour
MKT.marketOrder = 1 # this is the first and only market
MKT.nextMarketClearingTime = MKT.marketClearingTime + timedelta(hours=1)
MKT.initialMarketState = MarketState.Inactive
dayAhead = MKT
dayAhead.check_intervals()

ti = dayAhead.timeIntervals

# # Heat auction
# cooling_auction = Auction(energy_type='cooling')
# cooling_auction.name = 'coldwater_loop'
# heat_auction = Auction(energy_type='heat')
# heat_auction.name = 'steam_loop'

mTN.markets = [dayAhead]#, cooling_auction, heat_auction]


########################################################################################################

## Instantiate Neighbors and NeighborModels
Avista = Neighbor()
NB = Avista
NB.lossFactor = 0.01 # one percent loss at full power (only 99% is seen by TUR111 but you're paying for 100%, increasing effective price)
NB.mechanism = 'consensus'
NB.description = 'Avista electricity supplier node'
NB.maximumPower = 100000
NB.minimumPower = 0
NB.name = 'Avista'

AvistaModel = NeighborModel()
NBM = AvistaModel
NBM.name = 'Avista_model'
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = 0.0
NBM.friend = False
NBM.transactive = True
# set default vertices using integration method, production_cost_from_vertices() helper function which does square law for losses
default_vertices = [Vertex(marginal_price=0.029, prod_cost = 0, power=0, continuity=True, power_uncertainty=0.0), Vertex(marginal_price=0.031, prod_cost = 300.0, power=100000, continuity=True, power_uncertainty=0.0)]
NBM.defaultVertices = [default_vertices]
NBM.activeVertices = [[]]
for t in ti:
    NBM.activeVertices[0].append(IntervalValue(NBM, t, Avista, MeasurementType.ActiveVertex, default_vertices[0]))
    NBM.activeVertices[0].append(IntervalValue(NBM, t, Avista, MeasurementType.ActiveVertex, default_vertices[1]))
# NBM.defaultVertices = [[]]
# for t in ti:
#     NBM.defaultVertices[0].append(IntervalValue(NBM, t, Avista, MeasurementType.ActiveVertex, default_vertices[0]))
#     NBM.defaultVertices[0].append(IntervalValue(NBM, t, Avista, MeasurementType.ActiveVertex, default_vertices[1]))
# NBM.activeVertices = NBM.defaultVertices
NBM.productionCosts = [[prod_cost_from_vertices(NBM, t, 0, energy_type=MeasurementType.PowerReal, market=dayAhead) for t in ti]]
NBM.object = NB
NB.model = NBM
Avista = NB
AvistaModel = NBM 

# define thermal auctions here
# thermal auctions are neighbors which only interact with thermal energy
# steam auction
SteamLoop = Neighbor()
NB = SteamLoop
NB.lossFactor = 0.01
NB.mechanism = 'consensus'
NB.description = 'district heating steam distribution loop'
NB.maximumPower = 100000
NB.minimumPower = -10000
NB.name = 'steam_loop'
NB.Tsupply = 250
NB.Treturn = 120
NB.naturalGasPrice = 0.01

HeatAuctionModel = NeighborModel(measurementType=[MeasurementType.Heat])
NBM = HeatAuctionModel
NBM.name = 'steam_loop_model'
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = [0.0]
NBM.friend = True
NBM.transactive = True
default_vertices =[Vertex(marginal_price=-0.01, prod_cost = 0, power=-10000, continuity=True, power_uncertainty=0.0), Vertex(marginal_price=0.01, prod_cost = 100.0, power=10000, continuity=True, power_uncertainty=0.0)]
NBM.defaultVertices =  [default_vertices]#[[IntervalValue(NBM, t, HeatAuctionModel, MeasurementType.ActiveVertex, vert) for t in ti] for vert in default_vertices]
NBM.activeVertices =  [[IntervalValue(NBM, t, HeatAuctionModel, MeasurementType.ActiveVertex, vert) for t in ti] for vert in default_vertices]
NBM.productionCosts = [[prod_cost_from_vertices(NBM, t, 0, energy_type=MeasurementType.Heat, market=dayAhead) for t in ti]]

NBM.object = NB
NB.model = NBM
SteamLoop = NB
HeatAuctionModel = NBM

# cold water auction
ColdWaterLoop = Neighbor()
NB = ColdWaterLoop
NB.lossFactor = 0.01
NB.mechanism = 'consensus'
NB.description = 'district cooling cold water loop'
NB.maximumPower = 100000
NB.minimumPower = -10000
NB.name = 'water_loop'
NB.Tsupply = 4
NB.Treturn = 15

CoolAuctionModel = NeighborModel(measurementType=[MeasurementType.Cooling])
NBM = CoolAuctionModel
NBM.name = 'water_loop_model'
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = [0.0]
NBM.friend = True
NBM.transactive = True
default_vertices = [Vertex(marginal_price=-0.02, prod_cost = 0, power=-10000, continuity=True, power_uncertainty=0.0), Vertex(marginal_price=0.02, prod_cost = 200.0, power=10000, continuity=True, power_uncertainty=0.0)]
NBM.defaultVertices =  [default_vertices]#[[IntervalValue(NBM, t, CoolAuctionModel, MeasurementType.ActiveVertex, vert) for t in ti] for vert in default_vertices]#, Vertex(marginal_price=0.02, prod_cost = 300.0, power=10000, continuity=True, power_uncertainty=0.0)]]
NBM.activeVertices = [[IntervalValue(NBM, t, CoolAuctionModel, MeasurementType.ActiveVertex, vert) for t in ti] for vert in default_vertices]
NBM.productionCosts = [[prod_cost_from_vertices(NBM, t, 0, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti]]

NBM.object = NB
NB.model = NBM
ColdWaterLoop = NB
CoolAuctionModel = NBM

#create list of transactive neighbors to my transactive node
mTN.neighbors = [Avista, SteamLoop, ColdWaterLoop]

########################################################################################################

## instantiate each LocalAsset and its LocalAssetModel
# a LocalAsset is "owned" by myTransactiveNode and is managed
# and represented by a LocalAssetModel. There must be a one to one
# correspondence between a model and its asset
SCUE = LocalAsset()
LA = SCUE
LA.name = 'SCUE'
LA.description = 'Smith Center for Undergraduate Education: a new building with flexible loads'
LA.maximumPower = [0,0,0] # load is negative power [kW] and this building has no production capacity
LA.minimimumPower = [-10000, -10000, -10000]

SCUEModel = FlexibleBuilding()
LAM = SCUEModel
LAM.name = 'SCUE'
LAM.defaultPower = [-100.0, -100.0, -100.0]
LAM.thermalAuction = [SteamLoop, ColdWaterLoop]
LAM.create_default_vertices(ti, dayAhead)# when creating flexibility, the first vertex should be largest demand
LAM.productionCosts = [[prod_cost_from_vertices(LAM, t, 0, energy_type=MeasurementType.PowerReal, market=dayAhead) for t in ti],\
    [prod_cost_from_vertices(LAM, t, 1, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti],\
        [prod_cost_from_vertices(LAM, t, 1, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti]]
LA.model = LAM 
LAM.object = LA 
SCUE = LA
SCUEModel = LAM 


mTN.localAssets = [SCUE]

#############################################################################
## Additional setup script
# the following methods would normally be called soon after the above script
# to launch the system
# 
# call the Market method that will instantiate active future time intervals
dayAhead.check_intervals()

# call the information service that predicts and stores outdoor temps
PullmanTemperatureForecast.update_information(dayAhead)

# recieve any transactive signals sent to myTransactiveNode from its
# TransactiveNeighbors.
AvistaModel.receive_transactive_signal(TUR111)
CoolAuctionModel.receive_transactive_signal(TUR111)
HeatAuctionModel.receive_transactive_signal(TUR111)

#balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method
dayAhead.balance(TUR111)

# myTransactiveNode must prepare a set of TransactiveRecords for each of 
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
AvistaModel.prep_transactive_signal(dayAhead, TUR111)
CoolAuctionModel.prep_transactive_signal(dayAhead, TUR111)
HeatAuctionModel.prep_transactive_signal(dayAhead, TUR111)


# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor.
AvistaModel.send_transactive_signal(TUR111)
CoolAuctionModel.send_transactive_signal(TUR111)
HeatAuctionModel.send_transactive_signal(TUR111)

# invoke the market object to sum all powers as will be needed by the 
# net supply/demand curve
dayAhead.assign_system_vertices(TUR111)

# view the system supply/demand curve
dayAhead.view_net_curve(0)
dayAhead.view_net_curve(0, energy_type=MeasurementType.Heat)
dayAhead.view_net_curve(0, energy_type=MeasurementType.Cooling)
