## PnnlCampusAgent Script
# PNNL Campus's perspective in PNNL transactive campus system

# This script is used to initialize the Transactive Campus computational
# agent from provided base classes.

## Instantiate myTransactiveNode ******************************************
# This states the single perspective of the computational agent that is
# being configured. Each computational agent must complete a configuration
# script according to its unique perspective in the transactive network.
# *************************************************************************

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


## PNNL CAMPUS < myTransactiveNode
PnnlCampus = myTransactiveNode()  # Instantiate myTransactiveNode object
mTN = PnnlCampus  # Use abbreviation "mTN" for property assignments

mTN.description = 'PNNL Campus Transactive Node, Richland, WA'
mTN.name = 'PnnlCampus'  # a meaningful text name

## Instantiate each MeterPoint ********************************************
# A MeterPoint object is responsible for a current measurement or
# calculated value. Any MeterPoint that is used by models or objects should
# be defined here and accessible by myTransactiveNode. Meterpoints should
# be defined early in this script because a MeterPoint may be referenced by
# InformationServiceModels and other objects and classes.
# *************************************************************************

## PNNL ELECTRICITY METER < MeterPoint
# NOTE: Many more details must be included if and when we receive real-time
# metering of PNNL campus power.
PnnlElectricityMeter = MeterPoint()  # Instantiate an electricity meter
MP = PnnlElectricityMeter
MP.description = 'meters remaining COR power to the PNNL campus'
MP.measurementType = MeasurementType.PowerReal
MP.name = 'PnnlElectricityMeter'
MP.measurementUnit = MeasurementUnit.kWh

## Provide a cell array of the MeterPoint objects to myTransactiveNode.
# NOTE: Models and objects that use these meters are ALSO expected to
# possess such a list.
mTN.meterPoints = [PnnlElectricityMeter]

## Instantiate each InformationServiceModel *******************************
# An InformationServiceModel may be queried for information. It is often a
# Web information service, but is not necessarily a Web information
# service. This class is similar to MeterPoint, which should be used for
# simple metered data and calculations, but it includes model prediction
# for future time intervals.
# InformationServiceModels should be defined early in this script because
# they may be referenced by many other objects and models.
# *************************************************************************

## RICHLAND TEMPERATURE FORECAST < InformationServiceModel
# Uses a subclass that invokes Weather Underground forecasts.
# A constructor assigns properties description, informationType,
# informationUnits, license, name, nextScheduledUpdate,
# serviceExpirationDate, and updateInterval.
RichlandTemperatureForecast = TemperatureForecastModel()
ISM = RichlandTemperatureForecast

ISM.name = 'RichlandTemperatureForecast'
#   The next scheduled information update is initialized by constructor
#   method, but it's good practice to run method update_infromation() at
#   the end of this script.
ISM.predictedValues = []  #IntervalValue.empty  # dynamically assigned

## Provide a cell array of the InformationServiceModel objects to myTransactiveNode.
mTN.informationServiceModels = [RichlandTemperatureForecast]

## Instantiate each LocalAsset and its LocalAssetModel ********************
# A LocalAsset is "owned" by myTransactiveNode. A LocalAssetModel manages
# and represents its LocalAsset. There must be a one-to-one correspondence
# between a LocalAssetModel and its LocalAsset.
# *************************************************************************

## INELASTIVE BUILDINGS OBJECT < LocalAsset
InelasticBuildings = LocalAsset()  # Instantiate a LocalAssetModel
LA = InelasticBuildings  # Use abbreviation "LA" to assign properties

LA.description = 'PNNL Campus buildings that are not responsive'
LA.maximumPower = 0  # Remember that a load is a negative power [kW]
LA.minimumPower = -2 * 8200  # Assume twice the averag PNNL load [kW]
LA.name = 'InelasticBuildings'
#LA.subclass = LA.__class__

## INELASTIC BUILDINGS MODEL < LocalAssetModel
InelasticBuildingsModel = LocalAssetModel()
LAM = InelasticBuildingsModel  # Use abbrev. "LAM" to assign properties

# These properties are introduced by the LocalAssetModel class:
LAM.engagementCost = [0, 0, 0]  # Transition costs irrelevant

# These parameters are inherited from the AbstractModel class:
LAM.name = 'InelasticBuildingsModel'
LAM.defaultPower = -6000  # [kW]
LAM.defaultVertices = [Vertex(0, 0, -6000.0, 1)]

## Have the LocalAsset and LocalAssetModel reference one another
LA.model = LAM
LAM.object = LA

## SOLAR PV OBJECT < SolarPvResource < LocalAsset
SolarPv = SolarPvResource()  # Which is a LocalAsset subclass
LA = SolarPv  # Use abbrev. "LA" to assign properties

# These properties are inherited from the AbstractObject class:
LA.description = '120 kW solar PV site on the PNNL campus'
LA.maximumPower = 120.0  # [avg.kW]
LA.minimumPower = 0.0  # [avg.kW]
LA.name = 'SolarPv'
#LA.subclass = LA.__class__

## SOLAR PV MODEL < SolarPvResouceModes < LocalAssetModel
SolarPvModel = SolarPvResourceModel()  # Which is a LocalAssetModel subclass
LAM = SolarPvModel  # Use abbrev. "LAM" to assign properties

# These properties are inherited from the SolarPvResourceModel class:
LAM.cloudFactor = 1.0  # dimensionless

# These properties are inherited from the LocalAssetModel class:
LAM.engagementCost = [0, 0, 0]

# These properties are inherited from the AbstractModel class:
LAM.name = 'SolarPvModel'
LAM.defaultPower = 0.0  # [avg.kW]
LAM.defaultVertices = [Vertex(0, 0, 30.0, True)]
LAM.costParameters = [0, 0, 0]

## Allow object and model to cross reference one another
LA.model = LAM
LAM.object = LA

## Provide lists of LocalAssets to myTransactiveNode
# NOTE: This is now a cell array. Checks are performed to ensure that cell
# objects are derived from class LocalAsset.
mTN.localAssets = [InelasticBuildings, SolarPv]

## Instantiate Markets ****************************************************
# Markets specify TimeIntervals and when they are active. Additional
# Markets may be instantiated where (1) a complex series of sequential
# markets must be created, or (2) the durations of TimeIntervals change
# within the future horizon.
# *************************************************************************

## DAYAHEAD MARKET
dayAhead = Market()  # Instantiate Market object
MKT = dayAhead  # Use abbrev. "MKT" to assign properties

MKT.commitment = False
MKT.converged = False
MKT.defaultPrice = 0.04  # [$/kWh]
MKT.dualityGapThreshold = 0.001  # [0.02 = 2#]
MKT.futureHorizon = timedelta(hours=24)  # Projects 24 hourly future intervals
MKT.initialMarketState = MarketState.Inactive
MKT.intervalDuration = timedelta(hours=1)  # [h] Intervals are 1 h long
MKT.intervalsToClear = 1  # Only one interval at a time
MKT.marketClearingInterval = timedelta(hours=1)  # [h]
MKT.marketClearingTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # Aligns with top of hour
MKT.marketOrder = 1  # This is first and only market
MKT.name = 'dayAhead'
#MKT.nextMarketClearingTime = datetime('now') + 1 / 24 - minute(datetime('now')) / 1440 - second(datetime('now')) / 86400  # Next top of hour
MKT.nextMarketClearingTime = MKT.marketClearingTime + timedelta(hours=1)

## Provide a list of Markets to myTransactiveNode.
# NOTE: This is now a cell array, so its members should be referenced using
# curly braces.
mTN.markets = [dayAhead]

## Instantiate Neighbors and NeighborModels *******************************
# Neighbors are remote entities with which myTransactiveNode must interact.
# A NeighborModel manages an interface to and represents its Neighbor.
# There is a one-to-one correspondence between a Neighbor and its
# NeighborModel. A transactive Neighbor is committed to communicate
# transactive signals and is indicated by making property "transactive"
# TRUE in its NeighborModel.
# *************************************************************************

## SEB BUILDING < Neighbor (transactive)
SebBldg = Neighbor()  # Instantiate a Neighbor object
NB = SebBldg  # Use abbrev. "NBR" to assign properties

# These properties are inherited from the Neighbor class:
NB.lossFactor = 0.01  # i.e., 1# loss
NB.mechanism = 'consensus'

# These properties are inherited from the AbstractObject class:
NB.description = 'SEB Building on the PNNL Campus'
NB.maximumPower = 0.0  # Remember loads have negative power [avg.kW]
NB.minimumPower = -200  # [avg.kW]
NB.name = 'SebBldg'

## SEB BUILDING MODEL < NeighborModel
SebBldgModel = NeighborModel()  # Instantiate NeighborModel object
NBM = SebBldgModel  # Use abbrev. "NBM" to assign properties

# These properties are inherited from the NeighborModel class:
NBM.converged = False  # to be dynamically assigned
NBM.convergenceThreshold = 0.02  # i.e., 2#
NBM.effectiveImpedance = 0.0  # Not yet implemented
NBM.friend = True
NBM.transactive = True

# These properties are inherited from the AbstractModel class:
NBM.name = 'SebBldgModel'
NBM.defaultPower = -100  # [avg.kW]
NBM.defaultVertices = [Vertex(float("inf"), 0, -100.0, True)]
NBM.costParameters = [0, 0, 0]

## Allow the object and model to cross reference one another.
NBM.object = NB
NB.model = NBM

## SIGMA I BUILDING < Neighbor
Sigma1Bldg = Neighbor()  # Instantiate Neighbor object
NB = Sigma1Bldg  # Use abbrev. "NBR" to assign properties

# These properties are inherited from the Neighbor class:
NB.lossFactor = 0.01  # i.e., 1# loss
NB.mechanism = 'consensus'

# These properties are inherited from the AbstractObject class:
NB.description = 'Sigma I Building on the PNNL Campus'
NB.maximumPower = 0.0  # Remember loads have negative power [avg.kW]
NB.minimumPower = -200  # [avg.kW]
NB.name = 'Sigma1Bldg'

## Sigma I Building Model
Sigma1BldgModel = NeighborModel()  # Instantiate NeighborModel object
NBM = Sigma1BldgModel  # Use abbrev. "NBM" to assign properties

# These properties are inherited from the NeighborModel class:
NBM.converged = False  # to be dynamically assigned
NBM.convergenceThreshold = 0.02  # i.e., 2#
NBM.effectiveImpedance = 0.0  # Not yet implemented
NBM.friend = True
NBM.transactive = True

# These properties are inherited from the AbstractModel class:
NBM.name = 'Sigma1BldgModel'
NBM.defaultPower = -100  # [avg.kW]
NBM.defaultVertices = [Vertex(float("inf"), 0, -100.0, True)]
NBM.costParameters = [0, 0, 0]

## Allow the object and model to cross reference one another.
NBM.object = NB
NB.model = NBM

## RTL BUILDING < Neighbor
RtlBldg = Neighbor()  # Instantiate Neighbor object
NB = RtlBldg  # Use abbrev. "NBR" to assign properties

# These properties are inherited from the Neighbor class:
NB.lossFactor = 0.01  # i.e., 1# loss
NB.mechanism = 'consensus'

# These properties are inherited from the AbstractObject class:
NB.description = 'RTL Building on the PNNL Campus'
NB.maximumPower = 0.0  # Remember loads have negative power [avg.kW]
NB.minimumPower = -200  # [avg.kW]
NB.name = 'RtlBldg'

## RTL BUILDING MODEL < NeighborModel
RtlBldgModel = NeighborModel()  # Instantiate NeighborModel object
NBM = RtlBldgModel  # Use abbrev. "NBM" to assign properties

# These properties are inherited from the NeighborModel class:
NBM.converged = False  # to be dynamically assigned
NBM.convergenceThreshold = 0.02  # i.e., 2#
NBM.effectiveImpedance = 0.0  # Not yet implemented
NBM.friend = True
NBM.transactive = True

# These properties are inherited from the AbstractModel class:
NBM.name = 'RtlBldgModel'
NBM.defaultPower = -100  # [avg.kW]
NBM.defaultVertices = [Vertex(float("inf"), 0, -100.0, True)]
NBM.costParameters = [0, 0, 0]

## Allow the object and model to cross reference one another.
NBM.object = NB
NB.model = NBM

## 3860 Building
Bldg3860 = Neighbor()  # Instantiate Neighbor object
NB = Bldg3860  # Use abbrev. "NBR" to assign properties

# These properties are inherited from the Neighbor class:
NB.lossFactor = 0.01  # i.e., 1# loss
NB.mechanism = 'consensus'

# These properties are inherited from the AbstractObject class:
NB.description = '3860 Building on the PNNL Campus'
NB.maximumPower = 0.0  # Remember loads have negative power [avg.kW]
NB.minimumPower = -200  # [avg.kW]
NB.name = 'Bldg3860'

## 3860 BUILDING MODEL < NeighborModel
Bldg3860Model = NeighborModel()  # Instantiate NeighborModel object
NBM = Bldg3860Model  # Use abbrev. "NBM" to assign properties

# These properties are inherited from the NeighborModel class:
NBM.converged = False  # to be dynamically assigned
NBM.convergenceThreshold = 0.02  # i.e., 2#
NBM.effectiveImpedance = 0.0  # Not yet implemented
NBM.friend = True
NBM.transactive = True

# These properties are inherited from the AbstractModel class:
NBM.name = 'Bldg3860Model'
NBM.defaultPower = -100  # [avg.kW]
NBM.defaultVertices = [Vertex(float("inf"), 0, -100.0, True)]
NBM.costParameters = [0, 0, 0]

## Allow the object and model to cross reference one another.
NBM.object = NB
NB.model = NBM

## CITY OF RICHLAND (COR) < Neighbor
Cor = Neighbor()
NB = Cor  # Use abbrev. "NBR" to assign properties

# These properties are inherited from the Neighbor class:
NB.lossFactor = 0.01  # i.e., 1# loss
NB.mechanism = 'consensus'

# These properties are inherited from the AbstractObject class:
NB.description = 'City of Richland (COR) electricity supplier node'
NB.maximumPower = 16400  # Remember loads have negative power [avg.kW]
NB.minimumPower = 0  # [avg.kW]
NB.name = 'Cor'

## CITY OF RICHLAND MODEL < NeighborModel
CorModel = NeighborModel()
NBM = CorModel  # Use abbrev. "NBM" to assign properties

# These properties are inherited from the NeighborModel class:
NBM.converged = False  # to be dynamically assigned
NBM.convergenceThreshold = 0.02  # i.e., 2#
NBM.effectiveImpedance = 0.0  # Not yet implemented
NBM.friend = False
NBM.transactive = True

# These properties are inherited from the AbstractModel class:
NBM.name = 'CorModel'
NBM.defaultPower = -100  # [avg.kW]
NBM.defaultVertices = [Vertex(0.046, 160, 0, True),
                       Vertex(0.048, 160 + 16400 * (0.046 + 0.5 * (0.048 - 0.046)), 16400, True)]
NBM.costParameters = [0, 0, 0]

## Allow the object and model to cross reference one another.
NBM.object = NB
NB.model = NBM

## Provide a list of TransactiveNeighbors to myTransactiveNode.
# NOTE: This is now a cell array. Its members must be referenced using
# curly braces.
mTN.neighbors = [SebBldg, Sigma1Bldg, RtlBldg, Bldg3860, Cor]

## Additional setup script ************************************************
# The following methods would normally be called soon after the above
# script to launch the system.

# Call the Market method that will instantiate active future time
# intervals.
dayAhead.check_intervals()

# Call the information service that predicts and stores outdoor
# temperatures for active time intervals.
RichlandTemperatureForecast.update_information(dayAhead)

# Receive any transactive signals sent to myTransactiveNode from its
# TransactiveNeighbors. For this matlab version, this is simply the process
# of reading a file that the neighbor might have prepared and made
# available to myTransactiveNode.
CorModel.receive_transactive_signal(PnnlCampus)
SebBldgModel.receive_transactive_signal(PnnlCampus)
# RtlBldgModel.receive_transactive_signal(PnnlCampus)
# Sigma1BldgModel.receive_transactive_signal(PnnlCampus)
# Bldg3860Model.receive_transactive_signal(PnnlCampus)

# Balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method.
dayAhead.balance(PnnlCampus)

# myTransactiveNode must prepare a set of TransactiveRecords for each of
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
CorModel.prep_transactive_signal(dayAhead, PnnlCampus)
SebBldgModel.prep_transactive_signal(dayAhead, PnnlCampus)
# RtlBldgModel.prep_transactive_signal(dayAhead,PnnlCampus)
# Sigma1BldgModel.prep_transactive_signal(dayAhead,PnnlCampus)
# Bldg3860Model.prep_transactive_signal(dayAhead,PnnlCampus)

# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor. In the matlab version, this is the creation (or
# updating) of a text file having TransactiveRecords as its rows.
CorModel.send_transactive_signal(PnnlCampus)
SebBldgModel.send_transactive_signal(PnnlCampus)
# RtlBldgModel.send_transactive_signal(PnnlCampus)
# Sigma1BldgModel.send_transactive_signal(PnnlCampus)
# Bldg3860Model.send_transactive_signal(PnnlCampus)

# This method invokes the Market object to sum all the powers as will be
# needed by the net supply/demand curve.
dayAhead.assign_system_vertices(PnnlCampus)

# The condition of the total system supply/demand curve may be viewed at
# any time. This methods creates a net supply/demand curve figure for the
# active time integer interval indicated by the argument.
dayAhead.view_net_curve(0)
