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
from inflexible_building import InflexibleBuilding
from flexible_building import FlexibleBuilding
from gas_turbine import GasTurbine
from boiler import Boiler
from vertex import Vertex
from helpers import prod_cost_from_vertices
from interval_value import IntervalValue

################################################################################
# create a neighbor model
SPU124 = myTransactiveNode()
mTN = SPU124
mTN.description = 'substation SPU124 feeds half of the grimes way steam plant\
    as well as Johnson hall and the east campus inflexible buildings'
mTN.name = 'S124'

# set up Avista power meter
SPU124_meter = MeterPoint()
MP = SPU124_meter
MP.description = 'meters SPU124 electric use from AVISTA'
MP.measurementType = MeasurementType.PowerReal
MP.measurement = MeasurementUnit.kWh
SPU124_meter = MP

# provide a cell array of all the MeterPoints to myTransactiveNode
mTN.meterpoints = [SPU124_meter]

# instantiate each information service model
# this is services that can be queried for information
# this includes model prediction for future time intervals
# Pullman Temperature Forecast <-- Information service model
PullmanTemperatureForecast = TemperatureForecastModel()
ISM = PullmanTemperatureForecast
ISM.name = 'PullmanTemperatureForecast'
ISM.predictedValues = [] # dynamically assigned

mTN.informationServiceModels = [PullmanTemperatureForecast]

################################################################################
## Instantiate makets
# Markets specify active TimeIntervals

## Day Ahead Market
dayAhead = Market(measurementType= [MeasurementType.PowerReal, MeasurementType.Heat, MeasurementType.Cooling])
MKT = dayAhead
MKT.name = 'S124_Market'
MKT.commitment = False # start without having commited any resources
MKT.converged = False # start without having converged
MKT.defaultPrice = [0.0551, 0.02, 0.03] # [$/kWh]
MKT.dualityGapThreshold = 0.001 #optimal convergence within 0.1Wh
MKT.futureHorizon = timedelta(hours=24)
MKT.intervalDuration = timedelta(hours=1)
MKT.intervalsToClear = 24
MKT.marketClearingTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) # align with top of hour
MKT.marketOrder = 1 # this is the first and only market
MKT.nextMarketClearingTime = MKT.marketClearingTime + timedelta(hours=1)
MKT.initialMarketState = MarketState.Inactive
dayAhead = MKT
dayAhead.check_intervals()

ti = dayAhead.timeIntervals

# Thermal loops are seen as neighbor nodes

mTN.markets = [dayAhead]

################################################################################

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
NBM.transactive = False
# set default vertices using integration method, production_cost_from_vertices() helper function which does square law for losses
default_vertices = [Vertex(marginal_price=0.0551, prod_cost = 0, power=0, continuity=True, power_uncertainty=0.0), Vertex(marginal_price=0.05511, prod_cost = 551.1, power=100000, continuity=True, power_uncertainty=0.0)]
NBM.defaultVertices = [default_vertices]
NBM.activeVertices = [[]]
for t in ti:
    NBM.activeVertices[0].append(IntervalValue(NBM, t, Avista, MeasurementType.ActiveVertex, default_vertices[0]))
    NBM.activeVertices[0].append(IntervalValue(NBM, t, Avista, MeasurementType.ActiveVertex, default_vertices[1]))
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


# SPU122 is a neighbor
SPU122 = Neighbor()
NB = SPU122
NB.lossFactor = 0.001
NB.mechanism = 'consensus'
NB.description = 'neighboring supstation that supports central campus and half of GWSP'
NB.maximumPower = 100000
NB.minimumPower = -100000
NB.name = 'S122'

SPU122Model = NeighborModel(measurementType=[MeasurementType.PowerReal])
NBM = SPU122Model
NBM.name = 'S122_Model'
NBM.converged = False
NBM.convergenceThreshold = 0.01
NBM.effectiveImpedance = [0.0]
NBM.friend = True
NBM.transactive = True

NBM.object = NB
NB.model = NBM
SPU122 = NB
SPU122Model = NBM

#create list of transactive neighbors to my transactive node
mTN.neighbors = [Avista, SteamLoop, ColdWaterLoop, SPU122]

#############################################################################
# instantiate each local asset and its local asset model
# a LocalAsset is "owned" by myTransactiveNode and is managed and 
# represented by a LocalAssetModel. There must be a one to one
# correspondence between a model and its asset

# add inflexible east campus buildings
EastCampusInflexibleLoads = LocalAsset()
LA = EastCampusInflexibleLoads
LA.name = 'EastCampus'
LA.description = 'Inflexible buildings with electric, heating, and cooling loads'
LA.maximumPower = [0, 0, 0]
LA.minimumPower = [-100000, -1000, -1000]

ECBModel = InflexibleBuilding()
ECBModel.name = 'EastCampus'
ECBModel.defaultPower = [-1000.0, 0, 0]
ECBModel.thermalAuction = [SteamLoop, ColdWaterLoop]
ECBModel.create_default_vertices(ti, dayAhead)
ECBModel.productionCosts = [[prod_cost_from_vertices(ECBModel, t, 0, energy_type=MeasurementType.PowerReal, market=dayAhead) for t in ti],\
    [prod_cost_from_vertices(ECBModel, t, 1, energy_type=MeasurementType.Heat, market=dayAhead) for t in ti],\
        [prod_cost_from_vertices(ECBModel, t, 1, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti]]
LA.model = ECBModel
EastCampusBuildings = LA
ECBModel.object = EastCampusBuildings

# add flexible Johnson hall building
JohnsonHall = LocalAsset()
LA = JohnsonHall
LA.name = 'JohnsonHall'
LA.description = 'flexible building with electric, heating, and cooling loads'
LA.maximumPower = [0, 0, 0]
LA.minimumPower = [-10000, -1000, -1000]

JHModel = FlexibleBuilding()
JHModel.name = 'JohnsonHall'
JHModel.default_power = [-500, 0, 0]
JHModel.thermalAuction = [SteamLoop, ColdWaterLoop]
JHModel.create_default_vertices(ti, dayAhead)
JHModel.productionCosts = [[prod_cost_from_vertices(JHModel, t, 0, energy_type=MeasurementType.PowerReal, market=dayAhead) for t in ti],\
    [prod_cost_from_vertices(JHModel, t, 1, energy_type=MeasurementType.Heat, market=dayAhead) for t in ti],\
        [prod_cost_from_vertices(JHModel, t, 1, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti]]

LA.model = JHModel
JHModel.object = LA
JohnsonHall = LA


# add gas turbine 2
gt2 = LocalAsset()
gt2.name = 'GT2'
gt2.description = 'CHP gas turbine at GWSP connected to SPU124'
gt2.maximumPower = [1500, 1500*2]
gt2.minimumPower = [0,0]

gt2Model = GasTurbine()
gt2Model.name = 'GT2'
gt2Model.thermalAuction = SteamLoop
gt2Model.size = 1500
gt2Model.ramp_rate = 1.3344e3
gt2Model.create_default_vertices(ti, dayAhead)
gt2Model.productionCosts = [[prod_cost_from_vertices(gt2Model, t, 1, energy_type=MeasurementType.PowerReal, market =dayAhead) for t in ti], [prod_cost_from_vertices(gt2Model, t, 0.6, energy_type=MeasurementType.Heat, market=dayAhead) for t in ti]]
gt2.model = gt2Model
gt2Model.object = gt2

# add boilers
# add boiler 2
boiler2 = LocalAsset()
boiler2.name = 'Boiler2'
boiler2.description = '2nd boiler at GWSP'
boiler2.maximumPower = [20000]
boiler2.minimumPower = [0]

boiler2Model = Boiler(name = 'Boiler2')
boiler2Model.size = 20000
boiler2Model.ramp_rate = 1333.3
boiler2Model.thermalAuction = SteamLoop
boiler2Model.create_default_vertices(ti, dayAhead)
boiler2Model.productionCosts = [[prod_cost_from_vertices(boiler2Model, t, 1, energy_type=MeasurementType.Heat, market=dayAhead) for t in ti]]
boiler2.model = boiler2Model
boiler2Model.object = boiler2

# add boiler 3
boiler3 = LocalAsset()
boiler3.name = 'Boiler3'
boiler3.description = '3rd boiler at GWSP'
boiler3.maximumPower = [20000]
boiler3.minimumPower = [0,0]

boiler3Model = Boiler(name='Boiler3')
boiler3Model.size = 20000
boiler3Model.ramp_rate = 1333.3
boiler3Model.thermalAuction = SteamLoop
boiler3Model.create_default_vertices(ti, dayAhead)
boiler3Model.productionCosts = [[prod_cost_from_vertices(boiler3Model, t, 1, energy_type=MeasurementType.Heat, market=dayAhead) for t in ti]]
boiler3.model = boiler3Model
boiler3Model.object = boiler3

# create list of local assets
mTN.localAssets = [EastCampusBuildings, JohnsonHall, gt2, boiler2, boiler3]

############################################################################
## additional setup script
# the following methods would normally be called soon after the above script
# to launch the system
# 
# call the Market method that will instantiate active future time intervals
dayAhead.check_intervals()

# call the information service that predicts and stores outdoor temps
PullmanTemperatureForecast.update_information(dayAhead)

# recieve any transactive signals sent to myTransactiveNode from its
# TransactiveNeighbors.
#AvistaModel.receive_transactive_signal(SPU124)
HeatAuctionModel.receive_transactive_signal(SPU124)
CoolAuctionModel.receive_transactive_signal(SPU124)

#balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method
dayAhead.balance(SPU124)

# myTransactiveNode must prepare a set of TransactiveRecords for each of 
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
AvistaModel.prep_transactive_signal(dayAhead, SPU124)
HeatAuctionModel.prep_transactive_signal(dayAhead, SPU124)
CoolAuctionModel.prep_transactive_signal(dayAhead, SPU124)

# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor.
#AvistaModel.send_transactive_signal(SPU124)
HeatAuctionModel.send_transactive_signal(SPU124)
CoolAuctionModel.send_transactive_signal(SPU124)

# invoke the market object to sum all powers as will be needed by the 
# net supply/demand curve
dayAhead.assign_system_vertices(SPU124)

# view the system supply/demand curve
dayAhead.view_net_curve(0)
dayAhead.view_net_curve(0, energy_type=MeasurementType.Heat)
dayAhead.view_net_curve(0, energy_type=MeasurementType.Cooling)