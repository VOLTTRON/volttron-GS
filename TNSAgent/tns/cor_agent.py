## COR Agent Script
# Transactive network configuration script from the perspective of the City
# of Richland (COR).
#
# This script is used to initialize the City of Richland computational
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

Cor = myTransactiveNode()  # a meaningful object name
mTN = Cor

mTN.description = 'City of Richland Electric Utility, Richland, WA'
mTN.name = 'Cor'  # a meaningful text name

## Instantiate each MeterPoint ********************************************
# A MeterPoint object is responsible for a current measurement or
# calculated value. Any MeterPoint that is used by models or objects should
# be defined here and accessible by myTransactiveNode. Meterpoints should
# be defined early in this script because a MeterPoint may be referenced by
# InformationServiceModels and other objects and classes.
# *************************************************************************

## BPA ELECTRICITY METER < MeterPoint
# NOTE: Many more details must be included if and when we receive real-time
# metering of the power received by City of Richland from BPA.
BpaElectricityMeter = MeterPoint()  # Instantiate an electricity meter
MP = BpaElectricityMeter
MP.description = 'meters BPA electricity to COR'
MP.measurementType = MeasurementType.PowerReal
MP.name = 'BpaElectricityMeter'
MP.measurementUnit = MeasurementUnit.kWh  # 'kWh'

## Provide a cell array of the MeterPoint objects to myTransactiveNode.
# NOTE: Models and objects that use these meters are ALSO expected to
# possess such a list.
mTN.meterPoints = [BpaElectricityMeter]

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

## Provide a cell array of the InformationServiceModel objects to
# myTransactiveNode.
mTN.informationServiceModels = [RichlandTemperatureForecast]

## Instantiate each LocalAsset and its LocalAssetModel ********************
# An asset is "owned" by myTransactiveNode. A local asset model manages and
# represents its asset. There must be a one-to-one correspondence between
# an asset and asset model.

## CITY OF RICHLAND LOAD < LocalAsset
# Source: https://www.ci.richland.wa.us/home/showdocument?id=1890
#   Residential customers: 23,768
#   Electricity sales in 2015:
#       Total:     100.0#   879,700,000 kWh     100,400 avg. kW)
#       Resident:   46.7    327,200,000          37,360
#       Gen. Serv.: 38.1    392,300,000          44,790
#       Industrial: 15.2    133,700,000          15,260
#       Irrigation:  2.4     21,110,000           2,410
#       Other:       0.6      5,278,000             603
#   2015 Res. rate: $0.0616/kWh
#   Avg. annual residential cust. use: 14,054 kWh
#   Winter peak, 160,100 kW (1.6 x average)
#   Summer peak, 180,400 kW (1.8 x average)
#   Annual power supply expenses: $35.5M
# *************************************************************************
CorLoad = LocalAsset()
LA = CorLoad

# These properties are inherited from the AbstractObject class:
LA.description = 'COR electric load that is not responsive'
LA.maximumPower = -50000  # [avg.kW]
LA.minimumPower = -200000  # [avg.kW] (est. twice the average COR load)
LA.name = 'CorLoad'
#LA.subclass = LA.__class__


## CITY OF RICHLAND TEMPERATURE-SENSITIVE LOAD MODEL < LocalAssetModel
# This models the bulk COR circuit excluding the PNNL campus.
# CorLoadModel = BulkTempRespLoadModel # which inherits from LocalAssetModel
CorLoadModel = OpenLoopRichlandLoadPredictor(RichlandTemperatureForecast)  #CorLoadForecast()
LAM = CorLoadModel

# These properties are unique to BulkTempRespLoadModel:
#     LAM.basePower                                   # accept default value
#     LAM.coolingRise                                 # accept default value
#     LAM.heatingRise                                 # accept default value
#     LAM.inflectionTemp                              # accept default value
#     LAM.scalingFactor = 80000 / LAM.basePower               # scale to COR

# These properties are inherited from AbstractModel class:
LAM.name = 'CorLoadModel'
LAM.defaultPower = -100420  # [avg.kW]
LAM.defaultVertices = [Vertex(float("inf"), 0.0, -100420.0)]
LAM.meterPoints = []  #MeterPoint.empty

## Allow the object and model to cross reference one another
LA.model = LAM
LAM.object = LA

## Provide cell array of LocalAssets to myTransativeNode
mTN.localAssets = [CorLoad]

## Instantiate each Market ************************************************
# A Market is required. Markets specify TimeIntervals and when they are
# active. Additional Markets may be instantiated where (1) a complex series
# of sequential markets must be created, or (2) the durations of
# TimeIntervals change within the future horizon.
# *************************************************************************

## DAYAHEAD MARKET < Market
dayAhead = Market()
MKT = dayAhead

MKT.commitment = False
MKT.converged = False
MKT.defaultPrice = 0.0428  # [$/kWh]
MKT.dualityGapThreshold = 0.001  # [0.02 = 2#]
#   NOTE: Function Hours() corrects behavior of Matlab function hours().
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

## Provide a cell array of Markets to myTransactiveNode.
mTN.markets = [dayAhead]

## Instantiate each Neighbor and Neighbor Model ***************************
# Neighbors are remote locations with which myTransactiveNode exchanges
# electricity. myTransactiveNode has limited ownership or control over
# their electricty usage or generation. There are transactive neighbors and
# non-transactive neighbors, as may be specified by the property
# Neighbor.transactive.
#
# Transactive neighbors (transactive = true) are members of the transactive
# system network. Transactive signals are sent to and received from
# transactive neighbors.
#
# Non-Transactive neighbors (transactive = False) are not members of the
# transactive network. They do  not exchange TransactiveSignals with
# myTransactiveNode.
#
# The neighbor model manages an interface to and represents its neighbor.
# There is a one-to-one correspondence between a Neighbor and its model.
# *************************************************************************

## PNNL CAMPUS < Neighbor
# Source https://search.proquest.com/docview/220465031?pq-origsite=gscholar
#  PNNL uses 72 x 10^6 kWh annually (8,200 avg. kW) (2008)
PnnlCampus = Neighbor()
NB = PnnlCampus

# These properties are inherited from the Neighbor class:
NB.mechanism = 'consensus'

# These properties are inherited from the AbstractObject class:
NB.description = 'Pacific Northwest National Laboratory (PNNL) Campus in Richland, WA'
NB.maximumPower = 0.0  # [avg.kW] will not import
NB.minimumPower = -16400  # [avg.kW] (twice annual average)
NB.name = 'PnnlCampus'

## PNNL CAMPUS MODEL < NeighborModel
PnnlCampusModel = NeighborModel()
NBM = PnnlCampusModel

# These properteis are inherited from the NeighborModel class:
NBM.converged = False
NBM.convergenceThreshold = 0.02  # [0.02 = 2#]
NBM.effectiveImpedance = 0.0  # Not yet implemented
NBM.friend = False  # PNNL is customer
NBM.transactive = True  # a transactive neighbor

# These properties are inherited from the AbstractModel class:
NBM.name = 'PnnlCampusModel'
NBM.defaultPower = -8200  # [avg.kW]
NBM.defaultVertices = [Vertex(0.045, 0.0, -8200.0)]

## Allow the object and model to cross reference one another.
NBM.object = NB
NB.model = NBM

## BPA < Neighbor
# BPA is not "transactive", meaning that we never expect for it to be a
# member of the transactive network or exchange transactive signals with
# the City of Richland (COR).
Bpa = Neighbor()
NB = Bpa

# These properties are inherited from the Neighbor class:
NB.lossFactor = 0.02  # 0.02 = 2#
NB.mechanism = 'consensus'

# These properties are inherited from the AbstractObject class:
NB.description = 'The Bonneville Power Administration as electricity supplier to the City of Richland, WA'
NB.maximumPower = 200800  # [avg.kW, twice the average COR load]
NB.minimumPower = 0.0  # [avg.kW, will not export]
NB.name = 'Bpa'

## BPA MODEL < NeighborModel
BpaModel = BulkSupplier_dc()
NBM = BpaModel

# These properties are inherited from the BulkSupplier_dc class:
#   DEMAND THRESHOLD:
#       By default, set a default demand threshold for the begining of the
#       month. BPA has a complex formula for this determinant, but we will
#       simply assign the threshold at about 150# of the average COR demand
#       (~75# of the maximum deliverable power)
NBM.demandThreshold = 0.75 * NB.maximumPower  # [avg.kW]

# These properties are inherited from the NeighborModel class:
NBM.converged = False  # Dynamically assigned
NBM.convergenceThreshold = 0  # Not yet implemented
NBM.effectiveImpedance = 0.0  # Not yet implemented
NBM.friend = False  # Separate business entity from COR
NBM.transactive = False  # Not a transactive neighbor

# These properties are inherited from the AbstractModel class:
NBM.name = 'BpaModel'
#   DEFAULT VERTICES
#       The first default vertex is, for now, based on the flat COR rate to
#       PNNL. The second vertex includes 2# losses at a maximum power that
#       is twice the average electric load for COR. This is helpful to
#       ensure that a unique price, power point will be found. In this
#       model the recipient pays the cost of energy losses.
#       The first vertex is based on BPA Jan HLH rate at zero power
#       importation.
d1 = Vertex(0, 0, 0)  # create first default vertex
d1.marginalPrice = 0.04196  # HLH BPA rate Jan 2018 [$/kWh]
d1.cost = 2000.0  # Const. price shift to COR customer rate [$/h]
d1.power = 0.0  # [avg.kW]
#       The second default vertex represents imported and lost power at a power
#       value presumed to be the maximum deliverable power from BPA to COR.
d2 = Vertex(0, 0, 0)  # create second default vertex
#       COR pays for all sent power but receives an amount reduced by
#       losses. This creates a quadratic term in the production cost and
#       a slope to the marginal price curve.
d2.marginalPrice = d1.marginalPrice / (1 - NB.lossFactor)  # [$/kWh]
#       From the perspective of COR, it receives the power sent by BPA,
#       less losses.
d2.power = (1 - NB.lossFactor) * NB.maximumPower  # [avg.kW]
#       The production costs can be estimated by integrating the
#       marginal-price curve.
d2.cost = d1.cost + d2.power * (d1.marginalPrice + 0.5 * (d2.marginalPrice - d1.marginalPrice))
# [$/h]
NBM.defaultVertices = [d1, d2]

#   COST PARAMTERS
#     A constant cost parameter is being used here to account for the
#     difference between wholesale BPA rates to COR and COR distribution
#     rates to customers like PNNL. A constant of $2,000/h steps the rates
#     from about 0.04 $/kWh to about 0.06 $/kWh. This may be refined later.
#     IMPORTANT: This shift has no affect on marginal pricing.
NBM.costParameters[0] = 2000.0  # [$/h]
NBM.meterPoints = [BpaElectricityMeter]

## Allow the object and model to cross reference one another
NBM.object = NB
NB.model = NBM

##   Provide a cell array of Neighbors to myTransactiveNode.
mTN.neighbors = [Bpa, PnnlCampus]

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
PnnlCampusModel.receive_transactive_signal(Cor)

# Balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method.
dayAhead.balance(Cor)

# myTransactiveNode must prepare a set of TransactiveRecords for each of
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
PnnlCampusModel.prep_transactive_signal(dayAhead, Cor)

# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor. In the matlab version, this is the creation (or
# updating) of a text file having TransactiveRecords as its rows.
PnnlCampusModel.send_transactive_signal(Cor)

# This method invokes the Market object to sum all the powers as will be
# needed by the net supply/demand curve.
dayAhead.assign_system_vertices(Cor)

# The condition of the total system supply/demand curve may be viewed at
# any time. This methods creates a net supply/demand curve figure for the
# active time integer interval indicated by the argument.
#dayAhead.view_net_curve(1)
