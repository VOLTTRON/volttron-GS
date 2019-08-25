## SEB BLDG AGENT SCRIPT
# Transactive network configuration script from the perspective of the SEB
# Bldg.

# This script is used to initialize the SEB Building's computational
# agent from provided base classes.

## Instantiate myTransactiveNode ******************************************
#   This states the single perspective of the computational agent that is
#   being configured. Each computational agent must complete a
#   configuration script according to its unique perspective in the
#   transactive network.
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


SebBldg = myTransactiveNode()  # a meaningful object name
mTN = SebBldg

mTN.description = 'SEB Building on the Pacific NorthwestNational Laboratory campus, Richland, WA'
mTN.name = 'SebBldg'  # a meaningful text name

## Instantiate each MeterPoint ********************************************
# A MeterPoint object is responsible for a current measurement or
# calculated value. Any MeterPoint that is used by models or objects should
# be defined here and accessible by myTransactiveNode. Meterpoints should
# be defined early in this script because a MeterPoint may be referenced by
# InformationServiceModels and other objects and classes.
# *************************************************************************

## SEB ELECTRICITY METER < MeterPoint
# NOTE: Many more details must be included if and when we receive real-time
# metering.
SebElectricityMeter = MeterPoint()  # Instantiate an electricity meter
MP = SebElectricityMeter
MP.description = 'meters the SEB electricity load'
MP.measurementType = MeasurementType.PowerReal
MP.name = 'SebElectricityMeter'
MP.measurementUnit = MeasurementUnit.kWh

## Provide a cell array of the MeterPoint objects to myTransactiveNode.
# NOTE: Models and objects that use these meters are ALSO expected to
# possess such a list.
mTN.meterPoints = [SebElectricityMeter]

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

## Instantiate each LocalAsset and its LocalAssetModel

# An asset is "owned" by myTransactiveNode. Energy consumed (or generated)
# by a local asset is valued at either its production costs (for a
# resource) or blended price of electricity (for a load). A local asset
# model manages and represents its asset. There must be a one-to-one
# correspondence between an asset and asset model.

## Unresponsive SEB Building load
BldgLoad = LocalAsset()
LA = BldgLoad

LA.description = 'SEB Building load that is not responsive'
LA.maximumPower = 0
LA.minimumPower = -200  # [avg.kW]
LA.name = 'BldgLoad'
#LA.subclass = LA.__class__

## Unresponsive SEB Building Load Model
BldgLoadModel = LocalAssetModel()
LAM = BldgLoadModel

LAM.defaultPower = -100
LAM.defaultVertices = [Vertex(float("inf"), 0, -100, True)]
LAM.informationServiceModels = []  #InformationServiceModel.empty
LAM.name = 'SebLoadModel'
LAM.totalDualCost = 0.0  # to be dynamically assigned
LAM.totalProductionCost = 0.0  # to be dynamically assigned

## Allow the object and model to cross reference one another
LA.model = LAM
LAM.object = LA

## Intelligent Load Control (ILC) System
IlcSystem = LocalAsset()
LA = IlcSystem

LA.description = 'Interactive Load Control (ILCO) system in the SEB Building'
LA.maximumPower = 0  # [avg.kW]
LA.meterPoints = []  #MeterPoint.empty
LA.minimumPower = -50  # [avg.kW]
LA.name = 'IlcSystem'
#LA.subclass = LA.__class__

## Intelligent Load Control Model
IlcSystemModel = LocalAssetModel()
# IlcSystemModel = IlcModel # Does not run yet with this model 2/5/18
LAM = IlcSystemModel

LAM.defaultPower = -50
LAM.defaultVertices = [Vertex(0.055, 0, -50, True), Vertex(0.06, 0, -25, True)]
LAM.informationServiceModels = []  #InformationServiceModel.empty
LAM.name = 'IlcSystemModel'
LAM.totalDualCost = 0.0  # dynamically assigned
LAM.totalProductionCost = 0.0  # dynamically assigned

## Allow the object and model to cross reference one another
LA.model = LAM
LAM.object = LA

## Provide cell array of LocalLoads to myTransativeNode
# NOTE: The elements of this cell array must be indexed using curly braces.
SebBldg.localAssets = [BldgLoad, IlcSystem]

## Instantiate each Market ************************************************
# A Market is required. Markets specify TimeIntervals and when they are
# active. Additional Markets may be instantiated where (1) a complex series
# of sequential markets must be created, or (2) the durations of
# TimeIntervals change within the future horizon.

## DAYAHEAD MARKET
dayAhead = Market()
MKT = dayAhead

MKT.commitment = False
MKT.converged = False
MKT.defaultPrice = 0.0428  # [$/kWh]
MKT.dualityGapThreshold = 0.0005  # [0.02 = 2#]
MKT.futureHorizon = timedelta(hours=24)  # Projects 24 hourly future intervals
MKT.initialMarketState = MarketState.Inactive
MKT.intervalDuration = timedelta(hours=1)  # [h] Intervals are 1 h long
MKT.intervalsToClear = 1  # Only one interval at a time
MKT.marketClearingInterval = timedelta(hours=1)  # [h]
MKT.marketClearingTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # Aligns with top of hour
MKT.marketOrder = 1  # This is first and only market
MKT.futureHorizon = timedelta(hours=24)  # Projects 24 hourly future intervals
MKT.initialMarketState = MarketState.Inactive
MKT.intervalDuration = timedelta(hours=1)  # [h] Intervals are 1 h long
MKT.intervalsToClear = 1  # Only one interval at a time
MKT.marketClearingInterval = timedelta(hours=1)  # [h]
MKT.marketClearingTime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # Aligns with top of hour


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
# Transactive neighbors (transactive = True) are members of the transactive
# system network. Transactive signals are sent to and received from
# transactive neighbors.
#
# Non-Transactive neighbors (transactive = False) are not members of the
# transactive network. They do  not exchange TransactiveSignals with
# myTransactiveNode.
#
# The neighbor model manages an interface to and represents its neighbor.
# There is a one-to-one correspondence between a Neighbor and its model.

## PNNL Campus
PnnlCampus = Neighbor()
NB = PnnlCampus

NB.lossFactor = 0.01
NB.maximumPower = 200
NB.minimumPower = 0
NB.description = 'Pacific Northwest National Laboratory (PNNL) Campus in Richland, WA'
NB.mechanism = 'consensus'
NB.name = 'PNNLCampus'

## PNNL Campus Model
PnnlCampusModel = NeighborModel()
NBM = PnnlCampusModel

NBM.converged = False  # dynamically assigned
NBM.convergenceThreshold = 0.02
NBM.defaultVertices = [Vertex(0.045, 25, 0, 1), Vertex(0.048, 0, 200, True)]
NBM.demandThreshold = 0.8 * NB.maximumPower
NBM.effectiveImpedance = 0.0
NBM.friend = False
NBM.meterPoints = []  #MeterPoint.empty
NBM.name = 'PnnlCampusModel'
NBM.totalDualCost = 0.0  # dynamically assigned
NBM.totalProductionCost = 0.0  # dynamically assigned
NBM.transactive = True

## Allow the object and model to cross reference one another.
NBM.object = NB  # Cross reference to object
NB.model = NBM  # Cross reference to model

## Provide a cell array of Neighbors to myTransactiveNode.
# NOTE: A cell array must be indexed using curly braces.
mTN.neighbors = [PnnlCampus]

## Additional setup script ************************************************
# The following methods would normally be called soon after the above
# script to launch the system.

# Receive any transactive signals sent to myTransactiveNode from its
# TransactiveNeighbors. For this matlab version, this is simply the process
# of reading a file that the neighbor might have prepared and made
# available to myTransactiveNode.
PnnlCampusModel.receive_transactive_signal(SebBldg)

# Balance supply and demand at myTransactiveNode. This is iterative. A
# succession of iterationcounters and duality gap (the convergence metric)
# will be generated until the system converges. All scheduled powers and
# marginal prices should be meaningful for all active time intervals at the
# conclusion of this method.
dayAhead.balance(SebBldg)

# myTransactiveNode must prepare a set of TransactiveRecords for each of
# its TransactiveNeighbors. The records are updated and stored into the
# property "mySignal" of the TransactiveNeighbor.
PnnlCampusModel.prep_transactive_signal(dayAhead, SebBldg)

# Finally, the prepared TransactiveRecords are sent to their corresponding
# TransactiveNeighbor. In the matlab version, this is the creation (or
# updating) of a text file having TransactiveRecords as its rows.
PnnlCampusModel.send_transactive_signal(SebBldg)

# This method invokes the Market object to sum all the powers as will be
# needed by the net supply/demand curve.
dayAhead.assign_system_vertices(SebBldg)

# The condition of the total system supply/demand curve may be viewed at
# any time. This methods creates a net supply/demand curve figure for the
# active time integer interval indicated by the argument.
#dayAhead.view_net_curve(1)