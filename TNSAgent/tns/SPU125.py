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
from boiler import Boiler
from chiller import Chiller
from vertex import Vertex
from helpers import prod_cost_from_vertices
from interval_value import IntervalValue

# create a neighbor model
SPU125 = myTransactiveNode()
mTN = SPU125
mTN.description = 'substation SPU125 feeds half of the College Ave Steam plant. \
                    including the West campus chillers, half of the west campus \
                    inflexible buildings, and the CASP boilers.'
mTN.name = 'S125'

# set up AVISTA power meter
SPU125_meter = MeterPoint()
MP = SPU125_meter
MP.description = 'meters half the CASP electric use from Avista'
MP.measurementType = MeasurementType.PowerReal
MP.measurement = MeasurementUnit.kWh
SUP125_meter = MP

# provide a cell array of all the MeterPoints to myTransactiveNode
mTN.meterpoints = [SPU125_meter]

# instantiate each information service model
# this is services that can be queried for information
# this includes model prediction for future time intervals
# Pullman Temperature Forecast <-- Information service model
PullmanTemperatureForecast = TemperatureForecastModel()
ISM = PullmanTemperatureForecast
ISM.name = 'PullmanTemperatureForecast'
ISM.predictedValues = [] # dynamically assigned

mTN.informationServiceModels = [PullmanTemperatureForecast]

#################################################################################
## Instantiate Markets

## Day Ahead Horizon Market
dayAhead = Market(measurementType=[MeasurementType.PowerReal, MeasurementType.Heat, MeasurementType.Cooling])
MKT = dayAhead
MKT.name = 'S125_Market'
MKT.commitment = False
MKT.converged = False
MKT.defaultPrice = [0.0551, 0.02, 0.03]
MKT.dualityGapThreshold = 0.001 # optimal convergence within 0.1Wh
MKT.futureHorizon = timedelta(hours=24)
MKT.intervalDuration = timedelta(hours=1)
MKT.intervalsToClear = 24
MKT.marketClearingTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) #align with top of hour
MKT.marketOrder = 1 # this is the first and only market
MKT.nextMarketClearingTime = MKT.marketClearingTime + timedelta(hours=1)
MKT.initialMarketState = MarketState.Inactive
dayAhead = MKT
dayAhead.check_intervals()

ti = dayAhead.timeIntervals
# Thermal Auctions are seen as neighbor nodes

mTN.markets = [dayAhead]

#################################################################################

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

#create list of transactive neighbors to my transactive node
mTN.neighbors = [Avista, SteamLoop, ColdWaterLoop]

######################################################################################
# instantiate each local Asset and its LocalAssetModel
# a LocalAsset is "owned" by myTransactiveNode and is managed and 
# represented by a LocalAssetModel. There must be a one to one correspondence
# between a model and its asset

# add inflexible west campus buildings
WestCampusBuildings = LocalAsset()
LA = WestCampusBuildings
LA.name = 'WestCampus'
LA.description = 'Inflexible buildings with electric, heating, and cooling loads'
LA.maximumPower = [0, 0, 0]
LA.minimumPower = [-10000, -1000, -1000]

WCBModel = InflexibleBuilding()
LAM = WCBModel
LAM.name = 'WestCampus'
LAM.defaultPower = [-1000.0, 0, 0]
LAM.thermalAuction = [SteamLoop, ColdWaterLoop]
LAM.create_default_vertices(ti, dayAhead)
LAM.productionCosts = [[prod_cost_from_vertices(LAM, t, 0, energy_type=MeasurementType.PowerReal, market=dayAhead) for t in ti],\
    [prod_cost_from_vertices(LAM, t, 1, energy_type=MeasurementType.Heat, market=dayAhead) for t in ti],\
        [prod_cost_from_vertices(LAM, t, 1, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti]]
LA.model = LAM
LAM.object = LA
WestCampusBuildings = LA
WCBModel = LAM

# add west campus chillers: carrier chiller1, york chiller1, york chiller3
carrierchiller1 = LocalAsset()
carrierchiller1.name = 'Carrier Chiller 1'
carrierchiller1.description = '1st chiller at the west chiller plant'
carrierchiller1.maximumPower = [7.279884675000000e+03, 0]
carrierchiller1.minimumPower = [0, -7.27/2]

carrierchiller1Model = Chiller(name='carrierchiller1', size = 7.279884675000000e+03)
carrierchiller1Model.ramp_rate = 4.8533e3
carrierchiller1Model.create_default_vertices(ti, dayAhead)
carrierchiller1Model.productionCosts = [[prod_cost_from_vertices(carrierchiller1Model, t, 1, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti],[prod_cost_from_vertices(carrierchiller1Model, t, -1, energy_type=MeasurementType.PowerReal, market=dayAhead) for t in ti]]
carrierchiller1.model = carrierchiller1Model
carrierchiller1Model.object = carrierchiller1

# add york chiller 1
yorkchiller1 = LocalAsset()
yorkchiller1.name = 'York Chiller 1'
yorkchiller1.description = '2nd chiller at the west chiller plant'
yorkchiller1.maximumPower = [5.268245045000001e+03, 0]
yorkchiller1.minimumPower = [0, -5.27/2]

yorkchiller1Model = Chiller(name='yorkchiller1',size=5.268245045000001e+03)
yorkchiller1Model.ramp_rate = 3.5122e3
yorkchiller1Model.create_default_vertices(ti, dayAhead)
yorkchiller1Model.productionCosts = [[prod_cost_from_vertices(yorkchiller1Model, t, 1, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti], [prod_cost_from_vertices(yorkchiller1Model, t, -1, energy_type=MeasurementType.PowerReal, market=dayAhead) for t in ti]]
yorkchiller1Model.object = yorkchiller1
yorkchiller1.model = yorkchiller1Model

# add york chiller 3
yorkchiller3 = LocalAsset()
yorkchiller3.name = 'York Chiller 3'
yorkchiller3.description = '3rd chiller at the west chiller plant'
yorkchiller3.maximumPower = [5.268245045000001e+03, 0]
yorkchiller3.minimumPower = [0, -5.27/2]

yorkchiller3Model = Chiller(name='yorkchiller3', size=5.268245045000001e+03)
yorkchiller3Model.ramp_rate = 3.5122e3
yorkchiller3Model.create_default_vertices(ti, dayAhead)
yorkchiller3Model.productionCosts = [[prod_cost_from_vertices(yorkchiller3Model, t, 1, energy_type=MeasurementType.Cooling, market=dayAhead) for t in ti], [prod_cost_from_vertices(yorkchiller3Model, t, -1, energy_type=MeasurementType.PowerReal, market=dayAhead) for t in ti]]
yorkchiller3Model.object = yorkchiller3
yorkchiller3.model = yorkchiller3Model

boiler1 = LocalAsset()
boiler1.name = 'Boiler1'
boiler1.description = 'first boiler on west campus'
boiler1.maximumPower = [20000]
boiler1.minimumPower = [0]

boiler1Model = Boiler(name = 'boiler1', size = 20000)
boiler1Model.ramp_rate = 1333.3
boiler1Model.create_default_vertices(ti, dayAhead)
boiler1Model.productionCosts = [[prod_cost_from_vertices(boiler1Model, t, 1, energy_type=MeasurementType.Heat, market=dayAhead) for t in ti]]
boiler1Model.object = boiler1
boiler1.model = boiler1Model



mTN.localAssets = [WestCampusBuildings, carrierchiller1, yorkchiller1, yorkchiller3]

###################################################################################################################
## Additional setup script
# the following methods would normally be called soon afer the above script to launch the system
#
# # call the Market method that will instantiate active future time intervals
dayAhead.check_intervals()

# call the information service that predicts and stores outdoor temps
PullmanTemperatureForecast.update_information(dayAhead)

# recieve any transactive signals sent to myTransactiveNode from its
# TransactiveNeighbors.
AvistaModel.receive_transactive_signal(SPU125)
HeatAuctionModel.receive_transactive_signal(SPU125)
CoolAuctionModel.receive_transactive_signal(SPU125)

#balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method
dayAhead.balance(SPU125)

# myTransactiveNode must prepare a set of TransactiveRecords for each of 
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
AvistaModel.prep_transactive_signal(dayAhead, SPU125)
HeatAuctionModel.prep_transactive_signal(dayAhead, SPU125)
CoolAuctionModel.prep_transactive_signal(dayAhead, SPU125)

# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor.
#AvistaModel.send_transactive_signal(SPU125)
HeatAuctionModel.send_transactive_signal(SPU125)
CoolAuctionModel.send_transactive_signal(SPU125)

# invokde the market object to sum all powers as will be needed by the
# net supply/demand curve
dayAhead.assign_system_vertices(SPU125)

# view the system supply/demand curve
dayAhead.view_net_curve(0)
dayAhead.view_net_curve(0, energy_type=MeasurementType.Heat)
dayAhead.view_net_curve(0, energy_type=MeasurementType.Cooling)


