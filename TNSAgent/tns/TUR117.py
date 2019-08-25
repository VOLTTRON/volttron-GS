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
#from solar_pv_resource import SolarPvResource
from solar_pv_resource_model import SolarPvResourceModel

# create a neighbor model
TUR117 = myTransactiveNode()
mTN = TUR117
mTN.description = 'substation TUR117 feeds the research park facility including the PV arrays there'
mTN.name = 'T117'

# set up AVISTA power meter
TUR117_meter = MeterPoint()
MP = TUR117_meter
MP.description = 'meters net electrical demand of research park'
MP.measurementType = MeasurementType.PowerReal
MP.measurement = MeasurementUnit.kWh
TUR117_meter = MP

# provide a cell array of all the MeterPoints to myTransactiveNode
mTN.meterpoints = [TUR117_meter]

# instantiate each information service model
# this is services that can be queried for information
# this includes model prediction for future time intervals
# Pullman Temperature Forecast <-- Information service model
PullmanTemperatureForecast = TemperatureForecastModel()
ISM = PullmanTemperatureForecast
ISM.name = 'PullmanTemperatureForecast'
ISM.predictedValues = [] # dynamically assigned

mTN.informationServiceModels = [PullmanTemperatureForecast]

##################################################################
## Instantiate electrical market
# this node does not transact thermal demands

## Day Ahead Market
dayAhead = Market()
MKT = dayAhead
MKT.name = 'T117_Market'
MKT.commitment = False # start without having commited any resources
MKT.converged = False # start without having converged
MKT.defaultPrice = [0.04] # [$/kWh]
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

mTN.markets = [dayAhead]

####################################################################################

## Instantiate Neighbors and NeighborModels
# this node is only neighbors with AVISTA
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

mTN.neighbors = [Avista]

###########################################################################################
# instantiate each Local Asset and its LocalAssetModel
# a LocalAsset is "owned" by myTransactiveNode and is managed and 
# represented by a LocalAssetModel. There must be a one to one
# correspondence between a model and its asset

# add inflexible research park load
ResearchPark = LocalAsset()
LA = ResearchPark
LA.name = 'ResearchPark'
LA.description = 'Inflexible electrical load from research park buildings'
LA.maximumPower = [10000]
LA.minimumPower = [-1000]

RPModel = InflexibleBuilding(energy_types=[MeasurementType.PowerReal])
RPModel.name = 'ResearchPark'
RPModel.defaultPower = [-100.0, 0, 0]
RPModel.thermalAuction = []
RPModel.update_active_vertex(ti, dayAhead)

ResearchPark = LA
RPModel.object = ResearchPark
ResearchPark.model = RPModel

# add ground PV
groundPV = LocalAsset()
groundPV.name = 'groundPV'
groundPV.description = 'Photovoltaic array, ground mounted at Research Park'
groundPV.maximumPower = [40]
groundPV.minimumPower = [0.0]

GPVModel = SolarPvResourceModel()
GPVModel.name = 'groundPV'
GPVModel.defaultVertices = [100, 0, 0]

groundPV.model = GPVModel
GPVModel.object = groundPV

# add rooftop PV
rooftopPV = LocalAsset()
rooftopPV.name = 'rooftopPV'
rooftopPV.description = 'Photovoltaic array, rooftop mounted on Research Park building'
rooftopPV.maximumPower = [60]
rooftopPV.minimumPower = [0]

RPVModel = SolarPvResourceModel()
RPVModel.name = 'rooftopPV'
RPVModel.defaultVertices = [100, 0, 0]

rooftopPV.model = RPVModel
RPVModel.object = rooftopPV

# make a list of local assets
mTN.localAssets = [ResearchPark, groundPV, rooftopPV]

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
AvistaModel.receive_transactive_signal(TUR117)

#balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method
dayAhead.balance(TUR117)

# myTransactiveNode must prepare a set of TransactiveRecords for each of 
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
AvistaModel.prep_transactive_signal(dayAhead, TUR117)

# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor.
AvistaModel.send_transactive_signal(TUR117)

# invoke the market object to sum all powers as will be needed by the 
# net supply/demand curve
dayAhead.assign_system_vertices(TUR117)

# view the system supply/demand curve
dayAhead.view_net_curve(0)