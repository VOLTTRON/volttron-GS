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
from chiller import Chiller

# create a neighbor model
TVW131 = myTransactiveNode()
mTN = TVW131
mTN.description = 'substation TVW131 feeds the east campus chillers,\
    clark hall and its chillers, and some inflexible east campus loads.'
mTN.name = 'T131'

# set up Avista power meter
TVW131_meter = MeterPoint()
MP = TVW131_meter
MP.description = 'meters power draw by east campus chillers, clark hall, and a few east campus loads'
MP.measurementType = MeasurementType.PowerReal
MP.measurement = MeasurementUnit.kWh
TVW131_meter = MP

# provide a cell array of all the Meterpoints to myTransactiveNode
mTN.meterpoints = [TVW131_meter]

# instantiate each information service model
# this is services that can be queried for information
# this includes model prediction for future time intervals
# Pullman Temperature Forecast <-- Information service model
PullmanTemperatureForecast = TemperatureForecastModel()
ISM = PullmanTemperatureForecast
ISM.name = 'PullmanTemperatureForecast'
ISM.predictedValues = [] # dynamically assigned

mTN.informationServiceModels = [PullmanTemperatureForecast]

#######################################################################
## Intantiate Markets
# Markets specify active TimeIntervals

## Day Ahead Market
dayAhead = Market(measurementType = [MeasurementType.PowerReal, MeasurementType.Heat, MeasurementType.Cooling])
MKT = dayAhead
MKT.name = 'T131_Market'
MKT.commitment = False # start without having commited any resources
MKT.converged = False # start without having converged
MKT.defaultPrice = [0.04, 0.02, 0.03] # [$/kWh]
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

ti = dayAhead.timeIntervals[0]
# Thermal Loops are seen as neighbor nodes

mTN.markets = [dayAhead]

######################################################################################################################

## instantiate neighbors and neighbor models
# this node only has the utility and thermal loops as neighbors
Avista = Neighbor()
NB = Avista
NB.lossFactor = 0.01
NB.mechanism = 'consensus'
NB.description = 'Avista electricity supplier node'
NB.maximumPower = 100000
NB.minimumPower = 0
NB.name = 'Avista'

AvistaModel = NeighborModel()
NBM = AvistaModel
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = 0.0
NBM.friend = False
NBM.transactive = True
NBM.object = NB
NB.model = NBM
Avista = NB
AvistaModel = NBM 

# thermal loops are considered neighbors
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
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = [0.0]
NBM.friend = True
NBM.transactive = True

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
NBM.converged = False
NBM.convergenceThreshold = 0.02
NBM.effectiveImpedance = 0.0
NBM.friend = True
NBM.transactive = True

NBM.object = NB
NB.model = NBM
ColdWaterLoop = NB
CoolAuctionModel = NBM

#create list of transactive neighbors to my transactive node
mTN.neighbors = [Avista, SteamLoop, ColdWaterLoop]

###########################################################################################
# instantiate each Local Asset and its LocalAssetModel
# a LocalAsset is "owned" by myTransactiveNode and is managed and 
# represented by a LocalAssetModel. There must be a one to one
# correspondence between a model and its asset

# add inflexible loads
EastCampusInflexibleLoads = LocalAsset()
LA = EastCampusInflexibleLoads
LA.name = 'EastCampus'
LA.description = 'Inflexible electrical loads on the east side of campus'
LA.maximumPower = [0,0,0]
LA.minimumPower = [-1000, -1000, -1000]

ECModel = InflexibleBuilding()
LAM = ECModel
LAM.name = 'EastCampus'
LAM.defaultPower = [-500.0, 0, 0]
LAM.thermalAuction = [SteamLoop, ColdWaterLoop]
LAM.update_active_vertex(ti, dayAhead)

LA.model = LAM
LAM.object = LA
EastCampusInflexibleLoads = LA
ECModel = LAM

# add Clark hall loads
ClarkHall = LocalAsset()
LA = ClarkHall
LA.name = 'ClarkHall'
LA.description = 'Clark hall has inflexible loads, but also has chillers'
LA.maximumPower = [0, 0, 0]
LA.minimumPower = [-1000, -1000, -1000]

CHModel = InflexibleBuilding()
CHModel.name = 'ClarkHall'
CHModel.defaultPower = [-500, 0, 0]
CHModel.thermalAuction = [SteamLoop, ColdWaterLoop]
CHModel.update_active_vertex(ti, dayAhead)

LA.model = CHModel
ClarkHall = LA
CHModel.object = ClarkHall

# add east campus chillers: carrier chiller 2, and carrier chiller 3
# add carrier chiller 2
carrierchiller2 = LocalAsset()
LA = carrierchiller2
LA.name = 'carrierchiller2'
LA.description = '1st east campus chiller'
LA.maximumPower = [4.853256450000000e+03, 0]
LA.minimumPower = [0, -4.85/2]

cc2Model = Chiller(name='carrierchiller2', size=4.853256450000000e+03)
cc2Model.ramp_rate = 3.2355e3
cc2Model.create_default_vertices()

LA.model = cc2Model
carrierchiller2 = LA
cc2Model.object = carrierchiller2

# add carrier chiller 3
carrierchiller3 = LocalAsset()
LA = carrierchiller3
LA.name = 'carrierchiller3'
LA.description = '2nd east campus chiller'
LA.maximumPower = [4.853256450000000e+03, 0]
LA.minimumPower = [0, -4.85/2]

cc3Model = Chiller(name='carrierchiller3', size=4.853256450000000e+03)
cc3Model.ramp_rate = 3.2355e3
cc3Model.create_default_vertices()

LA.model = cc3Model
carrierchiller3 = LA
cc3Model.object = carrierchiller3

# add cold water storage tank?

# create list of local assets
mTN.localAssets = [EastCampusInflexibleLoads, ClarkHall, carrierchiller2, carrierchiller3]

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
AvistaModel.receive_transactive_signal(TVW131)
HeatAuctionModel.receive_transactive_signal(TVW131)
CoolAuctionModel.receive_transactive_signal(TVW131)

#balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method
dayAhead.balance(TVW131)

# myTransactiveNode must prepare a set of TransactiveRecords for each of 
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
AvistaModel.prep_transactive_signal(dayAhead, TVW131)
HeatAuctionModel.prep_transactive_signal(dayAhead, TVW131)
CoolAuctionModel.prep_transactive_signal(dayAhead, TVW131)

# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor.
AvistaModel.send_transactive_signal(TVW131)
HeatAuctionModel.send_transactive_signal(TVW131)
CoolAuctionModel.send_transactive_signal(TVW131)

# invoke the market object to sum all powers as will be needed by the 
# net supply/demand curve
dayAhead.assign_system_vertices(TVW131)

# view the system supply/demand curve
dayAhead.view_net_curve(0)
dayAhead.view_net_curve(0, energy_type=MeasurementType.Heat)
dayAhead.view_net_curve(0, energy_type=MeasurementType.Cooling)