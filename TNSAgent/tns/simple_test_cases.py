# test cases
# this script is intended to test the thermal class structures
# the first set of tests is instantiation of each type
# the second set of tests is creating small networks with few components
# the third set of tests is running them in a receding horizon
import os
import pickle

from auction import Auction
from boiler import Boiler 
from chiller import Chiller 
from cold_energy_storage import ColdEnergyStorage 
from flexible_building import FlexibleBuilding 
from inflexible_building import InflexibleBuilding 
from gas_turbine import GasTurbine 
from thermal_agent_model import ThermalAgentModel

from vertex import Vertex
from transactive_record import TransactiveRecord
from neighbor import Neighbor
from neighbor_model import NeighborModel
from solar_pv_resource import SolarPvResource
from solar_pv_resource_model import SolarPvResourceModel
from myTransactiveNode import myTransactiveNode
from time_interval import TimeInterval


###################################################################
## test set 1: Instantiation
cooling_auction = Auction(energy_type='cooling')
cooling_auction.name = 'coldwater_loop'
heat_auction = Auction(energy_type='heat')
heat_auction.name = 'steam_loop'

boiler1 = Boiler()
boiler1.name = 'Boiler1'
boiler1.size = 20000
boiler1.ramp_rate = 1333.3
boiler1.thermalAuction = heat_auction
boiler1.create_default_vertices()
#boiler1.min_capacity = boiler1.size*0.25

boiler2 = boiler1
boiler2.name = 'Boiler2'
boiler2.create_default_vertices()
boiler3 = boiler1
boiler3.name = 'Boiler3'
boiler3.create_default_vertices()
boiler4 = boiler1
boiler4.name = 'Boiler4'
boiler4.create_default_vertices()
boiler5 = boiler1
boiler5.name = 'Boiler5'
boiler5.create_default_vertices()

yorkchiller1 = Chiller(name='yorkchiller1',size=5.268245045000001e+03)
yorkchiller1.thermalAuction = cooling_auction
yorkchiller1.ramp_rate = 3.5122e3
yorkchiller1.create_default_vertices()

yorkchiller3 = yorkchiller1 #york chillers 1 and 3 are the same
yorkchiller3.name = 'yorkchiller3'

carrierchiller1 = yorkchiller1
carrierchiller1.name = 'carrierchiller1'
carrierchiller1.size = 7.279884675000000e+03
carrierchiller1.ramp_rate = 4.8533e3
carrierchiller1.create_default_vertices()

carrierchiller2 = carrierchiller1
carrierchiller2.name = 'carrierchiller2'
carrierchiller2.size = 4.853256450000000e+03
carrierchiller2.ramp_rate = 3.2355e3
carrierchiller2.create_default_vertices()

carrierchiller3 = carrierchiller2 #carrier chillers 2 and 3 are the same
carrierchiller3.name = 'carrierchiller3'

carrierchiller4 = carrierchiller1
carrierchiller4.name = 'carrierchiller4'
carrierchiller4.size = 1.758426250000000e+03
carrierchiller4.ramp_rate = 1.1723e3
carrierchiller4.create_default_vertices()

tranechiller = yorkchiller1
tranechiller.name = 'tranechiller'
tranechiller.size = 1.415462794200000e+03
tranechiller.ramp_rate = 943.6419
tranechiller.create_default_vertices()

cwst = ColdEnergyStorage()
cwst.thermalAuction = cooling_auction
cwst.size = 2000000
cwst.ramp_rate = 6000000

#load in campus demand file

SCUE = FlexibleBuilding()
SCUE.name = 'SCUE'
SCUE.thermalAuction = [heat_auction, cooling_auction]
SCUE.create_default_vertices()

EastCampusBuildings = InflexibleBuilding()
EastCampusBuildings.name = 'EastCampus'
EastCampusBuildings.thermalAuction = [heat_auction, cooling_auction]
EastCampusBuildings.update_active_vertex()

WestCampusBuildings = InflexibleBuilding()
WestCampusBuildings.name = 'WestCampus'
WestCampusBuildings.thermalAuction = [heat_auction, cooling_auction]
WestCampusBuildings.update_active_vertex()

CentralCampusBuildings = InflexibleBuilding()
CentralCampusBuildings.name = 'CentralCampus'
CentralCampusBuildings.thermalAuction = [heat_auction, cooling_auction]
CentralCampusBuildings.update_active_vertex()

ResearchPark = InflexibleBuilding()
ResearchPark.name = 'ResearchPark'
ResearchPark.thermalAuction = [heat_auction, cooling_auction]
ResearchPark.update_active_vertex()

gt1 = GasTurbine()
gt1.name = 'gt1'
gt1.thermalAuction = heat_auction
gt1.size = 1000
gt1.create_default_vertices()
gt1.ramp_rate = 1.3344e3

gt2 = gt1
gt2.name = 'gt2'
gt2.size = 1000
gt2.ramp_rate = 1.3344e3
gt2.create_default_vertices()

gen3 = gt1
gen3.name = 'dieselgen'
gen3.size = 1000
gen3.ramp_rate = 666.6692
gen3.create_default_vertices()

print('instantiation possible')

##################################################################
# test set 2: make small networks

# establish one node per feeder: these functions are part of the original TNT
# create a neighbor
TUR111 = Neighbor()
NB = TUR111
NB.lossFactor = 0.01
NB.mechanism = 'consensus'
NB.description = 'AVISTA sub station'
NB.maximumPower = 16400
NB.minimumPower = -8200
NB.name = 'TUR111'
TUR111 = NB

# create a neighbor model
TUR111model = NeighborModel()
NBM = TUR111model
NBM.converged = False # model state is dynamically assigned
NBM.convergenceThreshold = 0.02 # convergence within 2 Wh
NBM.effectiveImpedance = 0.0 # impedance and reactive power not yet implemented
NBM.friend = True # all the substations feeding campus should not compete with each other
NBM.name = 'TUR111model'
NBM.defaultPower = 0 # [avg. kW]
NBM.defailtVertices = [Vertex (0.049, 160, 0, True), Vertex(0.051, 160 + 16400*(0.049+0.5*(0.049-0.051)), 16400, True)]
NBM.costParameters = [0, 0, 0]
TUR111model = NBM

# assign the model and neighbor object reference each other
TUR111model.object = TUR111
TUR111.model = TUR111model

#create all other neighbors with similar parameters
# create substation TUR131 neighbor
TUR131 = NB
TUR131.name = 'TUR131'
TUR131model = NBM
TUR131model.name = 'TUR131model'
TUR131model.object = TUR131
TUR131.model = TUR131model

# create substation TUR115 neighbor
TUR115 = NB
TUR115.name = 'TUR115'
TUR115model = NBM
TUR115model.name = 'TUR115model'
TUR115model.object = TUR115
TUR115.model = TUR115model

# create substation TUR116 neighbor
TUR116 = NB
TUR116.name = 'TUR116'
TUR116model = NBM
TUR116model.name = 'TUR116model'
TUR116model.object = TUR116
TUR116.model = TUR116model

# create substation TUR117 neighbor
TUR117 = NB
TUR117.name = 'TUR117'
TUR117model = NBM
TUR117model.name = 'TUR117model'
TUR117model.object = TUR117
TUR117.model = TUR117model

# create substation SPU122 neighbor
SPU122 = NB
SPU122.name = 'SPU122'
SPU122model = NBM
SPU122model.name = 'SPU122model'
SPU122model.object = SPU122
SPU122.model = SPU122model

# create substation SPU124 neighbor
SPU124 = NB
SPU124.name = 'SPU124'
SPU124model = NBM
SPU124model.name = 'SPU124model'
SPU124model.object = SPU124
SPU124.model = SPU124model 

# test 2a: TUR111 flexible building on cold water loop

# test 2b: TUR131b (chiller half) east chillers

# test 2c: TUR131a East chillers, Clark Hall

# test 2d: TUR115: CHP gas turbine, inflexible building

# test 2f: TUR116: west chillers, inflexible building

# test 2g: TUR117: research park PV and inflexible load


# test 2h: SPU122: gas turbine, cenral campus inflexible buildings

# test 2i: SPU124: gas turbine, boilers, east campus inflexible buildings

# test 2j: TUR131c: East chillers, Clark Hall, Cold Thermal Storage tank

###################################################################
# test set 3: connect network

# test 3a: TUR115 and SPU125

# test 3b: SPU122 and SPU124

# test 3c: TUR111 and TUR131 and TUR117

###################################################################
# test 4: entire network

###################################################################
# test 5: entire network with receding horizon
