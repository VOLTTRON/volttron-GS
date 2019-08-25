## WSU Campus Agent script
#WSU Campus's perspective in transactive campus system
# This model does not yey have characteristics representative of the WSU campus

# this script is used to intialize the Transactive Campus computational
# agent from provided base classes

from model import Model
from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from measurement_unit import MeasurementUnit
from interval_value import IntervalValue
from transactive_record import TransactiveRecord
from meter_point import MeterPoint
from market import Market
from market_state import MarketState
from time_interval import TimeInterval
from neighbor import Neighbor
from local_asset import LocalAsset
from local_asset_model import LocalAssetModel
from myTransactiveNode import myTransactiveNode
from bulk_supplier_dc import BulkSupplier_dc
from neighbor_model import NeighborModel
from temperature_forecast_model import TemperatureForecastModel
from openloop_richland_load_predictor import OpenLoopRichlandLoadPredictor
from solar_pv_resource import SolarPvResource
from solar_pv_resource_model import SolarPvResourceModel


## WSU CAMPUS < myTransactiveNode
wsuCampus = myTransactiveNode() #instantiate myTransactiveNode object
mTN = wsuCampus # use abbreviation mTN for my transactive node property assignment

mTN.description = 'WSU Campus Transactive Node, Pullman, WA'
mTN.name = 'WSUCampus'

# instantiate each meter pont object to get current measurement or calculated value
# meter points are defined early so that models or other objects may reference them

wsu_elec_P_meter = MeterPoint()
MP = wsu_elec_P_meter
MP.description = 'meters AVISTA power to WSU campus'
MP.measurementType = MeasurementType.PowerReal
MP.name = 'WSURealPowerMeter'
MP.measurement = MeasurementUnit.kWh
wsu_elec_P_meter = MP

# wsu_elec_Q_meter = MeterPoint()
# MP = wsu_elec_Q_meter
# MP.description = 'meters AVISTA power to WSU campus'
# MP.measurementType = MeasurementType.PowerReactive
# MP.name = 'WSUQPowerMeter'
# MP.measurement = MeasurementUnitkVAh
# wsu_elec_Q_meter = MP

## Provide a cell array of the MeterPoint objects to myTransactiveNode
# NOTE: Models and objects that use these meters are ALSO expected to possess such a list
mTN.meterPoints = [wsu_elec_P_meter] #, wsu_elec_Q_meter]

## Instantiate each Information Service Model
# the is a service that can be queried for information
# includes model prediction for future time intervals

## Pullman Temperature Forecast < Information service model
# uses a subclass that invokes weather underground forecasts
PullmanTemperatureForecast = TemperatureForecastModel()
ISM = PullmanTemperatureForecast
ISM.name = 'PullmanTemperatureForecast'
ISM.predictedValues = [] #dynamically assigned

mTN.informationServiceModels = [PullmanTemperatureForecast]

## instantiate each LocalAsset and its LocalAssetModel
# a LocalAsset is "owned" by myTransactiveNode and is managed
# and represented by a LocalAssetModel. There must be a one to one correspondence
# between a model and its asset

## Inelastic Buildings Object < LocalAsset
InelasticBuildings = LocalAsset() # Instantiate a LocalAssetModel
LA = InelasticBuildings
LA.description = 'WSU Campus buildings that do not have flexible loads or response capability'
LA.maximumPower = 0 # Remember that a load is a negative power [kW]
LA.minimumPower = -2 * 8200 # assume twice the average PNNL load [kW]
LA.name = 'InelasticBuildings'
InelasticBuildings = LA

## Inelastic Buildings Model < LocalAssetModel
InelasticBuildingsModel = LocalAssetModel()
LAM = InelasticBuildingsModel
LAM.engagementCost = [0,0,0] # no transition costs
LAM.name = 'InelasticBuildingsModel'
LAM.defaultPower = -6000 #[kW]
LAM.defaultVertices = [Vertex(0, 0, -6000.0, 1)]
InelasticBuildingsModel = LAM

#have them reference one another
InelasticBuildings.model = InelasticBuildingsModel
InelasticBuildingsModel.object = InelasticBuildings

## SOLAR PV OBJECT < SolarPvResource < LocalAsset
RooftopPv = SolarPvResource() # this is a LocalAsset subclass
LA = RooftopPv
LA.description = '30 kW solar PV site at WSUs Resarch Park rooftop'
LA.maximumPower = 30.0 # [avg. kW]
LA.minimumPower = 0.0 # [avg. kW]
LA.name = 'RooftopPv'
RooftopPv = LA
## SOLAR PV Model < SolarPVResourceModel < LocalAssetModel
RooftopPvModel = SolarPvResourceModel() # Which is a LocalAssetModel Subclass
LAM = RooftopPvModel
LAM.cloudFactor = 1.0
LAM.engagementCost = [0, 0, 0]
LAM.name = 'RooftopPvModel'
LAM.defaultPower = 0.0 # [avg. kW]
LAM.defaultVertices = [Vertex(0, 0, 30.0, True)]
LAM.costParameters = [0, 0, 0]
RooftopPvModel = LAM
#have them reference one another
RooftopPv.model = RooftopPvModel
RooftopPvModel.object = RooftopPv

## SOLAR PV OBJECT < SolarPvResource < Local Asset
GroundPv = SolarPvResource() # this is a Local Asset subclass
LA = GroundPv
LA.description = '45 kW PV site at WSUs Research Park lawn'
LA.maximumPower = 45.0 # [avg. kW]
LA.minimumPower = 0.0 # [avg. kW]
LA.name = 'GroundPv'
GroundPv = LA
## SOLAR PV Model < SolarPVResourceModel < LocalAssetModel
GroundPvModel = SolarPvResourceModel()
LAM = GroundPvModel
LAM.cloudFactor = 1.0
LAM.engagementCost = [0,0,0]
LAM.name = 'GroundPvModel'
LAM.defaultPower = 0.0 # [avg. kW]
LAM.defaultVertices = [Vertex(0,0,45.0, True)]
LAM.costParameters = [0, 0, 0]
GroundPvModel = LAM
#have them reference one another
GroundPv.model = RooftopPvModel
GroundPvModel.object = GroundPv


## Gas Turbine Object < LocalAsset
GasTurbine1 = LocalAsset()
LA = GasTurbine1
LA.description = 'A microturbine at the Campus Avenue Steam Plant'
LA.maximumPower = 1000 # [kW]
LA.minimumPower = 129.387 # may need to revise this to accomodate unit commitment
LA.name = 'GasTurbine1'
GasTurbine1 = LA
## Gas Turbine Model < LocalAssetModel
GasTurbine1Model = LocalAssetModel()
LAM = GasTurbine1Model
LAM.engagement = [323.4671,0,0] # start with no transition cost
LAM.name = 'GasTurbine1Model'
LAM.defaultPower = 800 # [kW]
LAM.defaultVertices = [Vertex(0, 0.05, 0, 1), Vertex(0, .05, 1000, 1)]
LAM.costParameters = [0.05, -0.03, 0.04]
GasTurbine1Model = LAM
#have them reference one another
GasTurbine1.model = GasTurbine1Model
GasTurbine1Model.object = GasTurbine1

## Gas Turbine Object < LocalAsset
GasTurbine2 = LocalAsset()
LA = GasTurbine2
LA.description = 'Second microturbine at the Campus Agenue Steam Plant'
LA.maximumPower = 1000 # [kW]
LA.minimumPower = 129.387
LA.name = 'GasTurbine2'
GasTurbine2 = LA
## Gas Turbine Model < LocalAssetModel
GasTurbine2Model = LocalAssetModel()
LAM = GasTurbine2Model
LAM.engagement = [323.4671, 0, 0]
LAM.name = 'GasTurbine2Model'
LAM.defaultPower = 800 # [kW]
LAM.defaultVertices = [Vertex(0, 0.05, 0, 1), Vertex(0, 0.05, 1000, 1)]
LAM.costParameters = [0.05, -0.03, 0.04]
GasTurbine2Model = LAM
#have them reference each other
GasTurbine2.model = GasTurbine2Model
GasTurbine2Model.object = GasTurbine2

## Provide a list of LocalAssets to myTransactiveNode
# NOTE: This is now a cell array. Checks are performed to ensure that cell
# objects are derived from class LocalAsset
mTN.localAssets = [InelasticBuildings, RooftopPv, GroundPv, GasTurbine1, GasTurbine2]


######################################################################################
## Instantiate Markets
# Markets specify active TimeIntervals

## Day Ahead Market
dayAhead = Market() # Instantiate Market Object
MKT = dayAhead
MKT.commitment = False #start without having commited any resources
MKT.converged = False #start without having converged
MKT.defaultPrice = 0.04 # [$/kWh]
MKT.dualityGapThreshold = 0.001 #optimal convergence within .1Wh
MKT.futureHorizon = timedelta(hours=24) # 24 hour horizon with hourly timesteps
MKT.initialMarketState = MarketState.Inactive
MKT.intervalDuration = timedelta(hours=1)
MKT.intervalsToClear = 1 # Only clear one interval at a time
MKT.marketClearingInterval = timedelta(hours=1)
MKT.marketClearingTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) #align with top of hour
MKT.marketOrder = 1 # This is the first and only market
MKT.name = 'dayAhead'
MKT.nextMarketClearingTime = MKT.marketClearingTime + timedelta(hours=1)

## Provide a list of Markets to myTransactiveNode
mTN.markets = [dayAhead]

#####################################################################################
## Instantiate Neighbors and NeighborModels
# Neighbors are remote entities with which myTransactiveNode must interact
# A MeighborModel manages an interface to and represents its Neighbor.
# There is a one-to-one correspondence between a Neighbor and its NeighborModel.
# A transactive Neighbor is committed to communicate transactive signals and is
# indicated by making property "transactive"
# TRUE in its NeighborModel

## AVISTA < Neighbor
Avista = Neighbor()
NB = Avista
NB.lossFactor = 0.01 # only real power losses
NB.mechanism = 'consensus'
NB.description = 'AVISTA utility electricity supplier node'
NB.maximumPower = 16400
NB.minimumPower = -8200
NB.name = 'AVISTA'
Avista = NB

## AVISTA MODEL < NeighborModel
AvistaModel = NeighborModel()
NBM = AvistaModel
NBM.converged = False # model should be dynamically assigned
NBM.convergenceThreshold = 0.02 # convergence within 2 Wh
NBM.effectiveImpedance = 0.0 # impedance and reactive power not yet implemented
NBM.friend = False #compete with other entities
NBM.transactive = True
NBM.name = 'AvistaModel'
NBM.defaultPower = 0 # [avg. kW]
NBM.defaultVertices = [Vertex (0.049, 160, 0, True), Vertex(0.051, 160 + 16400*(0.049+0.5*(0.049-0.051)), 16400, True)]
NBM.costParameters = [0, 0, 0]
AvistaModel = NBM

#make the object and model cross reference each other
AvistaModel.object = Avista
Avista.model = AvistaModel

## SCUE Building < Neighbor
# the SCUE building is on campus, but is flexible and directly connected to AVISTA
SCUEBuilding = Neighbor()
NB = SCUEBuilding
NB.lossFactor = 0.001 # only real power losses
NB.mechanism = 'consensus'
NB.description = 'Smith Center for Undergradute Education Building on WSU Campus'
NB.maximumPower = 0.0 # this building is a flexible load
NB.minimumPower = -300
NB.name = 'SCUE'
SCUEBuilding = NB

## SCUE Building Model < NeighborModel
SCUEBuildingModel = NeighborModel()
NBM = SCUEBuildingModel
NBM.converged = False #dynamically assigned
NBM.convergenceThreshold = 0.02 # convergence within 2 Wh
NBM.effectiveImpedance = 0.0 # impedance and reactive power not yet implemented
NBM.friend = True # don't compete with friendly entities, this feature is not yet enabled
NBM.transactive = True
NBM.name = 'SCUE'
NBM.defaultPower = -100
NBM.defaultVertices = [Vertex(0, -0.01, -300.0, True), Vertex(0, -0.01, 0.0, True)]
NBM.costParameters = [0, -0.01, 0]
SCUEBuildingModel = NBM

#make the object and model cross reference each other
SCUEBuilding.model = SCUEBuildingModel
SCUEBuildingModel.object = SCUEBuilding

## create list of transactive neighbors to myTransactiveNode
mTN.neighbors = [SCUEBuilding, Avista]

#######################################################################################################
## Additional Setup script
## The following methods would normal be called soon after the above script to launch the system

# Call the Market method that will instantiate active future time intervals
dayAhead.check_intervals()

# Call the information service that predicts and stores outdoor temperatures for active time intervals
PullmanTemperatureForecast.update_information(dayAhead)

# Recieve any transactie signals sent to myTransactiveNode from its TransactiveNeighbors
# pretend you don't have access to your neighbors info by reading a file that neighbor prepares
# and makes available to myTransactiveNode
AvistaModel.receive_transactive_signal(wsuCampus)
SCUEBuildingModel.receive_transactive_signal(wsuCampus)

# Balance supply and demand at myTransactiveNode
# This is iterative: iteration counters and duality gaps are generated as the system converges
# all scheduled power setpoints and marginal prices should be meaningful for all active time intervals
# at the conclusion of this method
dayAhead.balance(wsuCampus)

# myTransactiveNode must prepare a set of TransactiveRecords for each of its TransactiveNeighbors
# The records are updated and stored into the property "mySignal" of the TransactiveNeighbor
AvistaModel.prep_transactive_signal(dayAhead, wsuCampus)
SCUEBuildingModel.prep_transactive_signal(dayAhead, wsuCampus)

# Finally, the prepared TransactiveRecords are sent to their corresponding TransactiveNeighbor
# This is the creation of a text file with the TransactiveRecords as its rows
AvistaModel.send_transactive_signal(wsuCampus)
SCUEBuildingModel.send_transactive_signal(wsuCampus)

# use market object to sum all powers to find the net supply/demand curve
dayAhead.assign_system_vertices(wsuCampus)

# to view the supply/demand curve at any time:
dayAhead.view_net_curve(0)