############### Linear Programming WSU Dispatcher #################
###################################################################
# The intention of this script is to create dispatch setpoints for 
# the gas turbines, boilers, and chillers on WSU's campus to meet
# electrical and thermal loads. These dispatches are not optimal
# given the poor fidelity with which they model component efficiency
# curves. These dispatches also do not include the dispatch of the
# cold water energy storage tank on campus. All buildings are assumed
# to have fixed loads which are the inputs. This script does not
# include unit commitment.

# This script follows the sequence below:
# 0) read in load signal from csv?
# 1) create linear efficiency fits from component data
# 2) variables are defined and added to problem
# 3) constraint functions are defined and added to problem
# 4) objective function is defined and added to problem

# This script was written by Nadia Panossian at Washington State University
# and was last updated by:
# Nadia Panossian on 10/14/2019
# the author can be reached at nadia.panossian@wsu.edu

import itertools
import os
import xlrd
import csv
import datetime
import time
import numpy as np
import cvxpy

############# System parameters ######################################
start_date = datetime.datetime(2009, 1, 1, 0, 0, 0) # start on January 1st
T = 24 # 24 hour horizon
dt = 1 #hourly timesteps
allow_thermal_slack = False # there is no slack variable in heat or cooing equality
# cost rates
util_rate = 0.0551
gas_rate = 5.6173/293.07
diesel_rate = 24.0/12.5

def create_timestamp(year,month,day,length,dt=1):
    start = datetime.datetime(year,month,day,0,0,0)
    timestamp = [start]

    for add in range(1,length):
        next = start + datetime.timedelta(hours=add*dt)
        timestamp.insert(len(timestamp),next)
    return timestamp

############# read in demand #########################################
wb = xlrd.open_workbook(os.getcwd() +'\wsu_campus_2009_2012.xlsx')
dem_sheet = wb.sheet_by_index(0)
weather_sheet = wb.sheet_by_index(1)

tdb = []#dry bulb temp
irrad_dire_norm = []#direct normal irradiation
e = []
h = []
c = []
for i in range(1,T+1):
    e.append(dem_sheet.cell_value(i,0))
    h.append(dem_sheet.cell_value(i,1))
    c.append(dem_sheet.cell_value(i,2))

    tdb.append(weather_sheet.cell_value(i,0))
    irrad_dire_norm.append(weather_sheet.cell_value(i,1))

#heat has way more nans, so remove them
h = h[:37810]
timestamp = create_timestamp(2009,1,1,T,dt=dt)

# demand has one value for entire campus
demand = {'e': e, 'h':h, 'c':c}
weather = {'t_db': tdb, 'irrad_dire_norm': irrad_dire_norm}
testdata = {'demand': demand, 'weather':weather, 'timestamp':timestamp}

RANGE = -1

############# read in building with flexible demand #################
n_flex_buildings = 1
temp_ub = [[] for i in range(n_flex_buildings)]
temp_lb = [[] for i in range(n_flex_buildings)]
elec_neutral = [[] for i in range(n_flex_buildings)]
cool_neutral = [[] for i in range(n_flex_buildings)]
heat_neutral = [[] for i in range(n_flex_buildings)]
cool_v_temp = [[] for i in range(n_flex_buildings)]
heat_v_temp = [[] for i in range(n_flex_buildings)]
elec_v_temp = [[] for i in range(n_flex_buildings)]
cost_v_temp = np.zeros((n_flex_buildings,T))

for i in range(n_flex_buildings):
    file_b = open("flexible_building_data.txt", "r") #this loop will need to be changed if multiple buildings
    # read in all building data for horizon
    headings = file_b.readline()
    for t in range(T):
        neutral = [float(val) for val in file_b.readline()[:-2].split(", ")]# neutral
        cold = [float(val) for val in file_b.readline()[:-2].split(", ")]# a little cold
        hot = [float(val) for val in file_b.readline()[:-2].split(", ")]# a little hot
        # make lists for boundaries on temperature
        temp_ub[i].append(hot[1])
        temp_lb[i].append(cold[1])
        #temp_netral[i].append(neutral[1])
        # make list loads at each temperature setpoint
        # electrical loads
        elec_neutral[i].append(neutral[2])
        elec_cold = cold[2]-neutral[2]
        elec_hot = hot[2]-neutral[2] 
        # cooling loads
        cool_neutral[i].append(neutral[3])
        cool_cold = cold[3]-neutral[3]
        cool_hot = hot[3]-neutral[3]
        # heating loads
        heat_neutral[i].append(neutral[4])
        heat_cold = cold[4]
        heat_hot = hot[4]
        # discomfort cost
        cost_cold = cold[5]
        cost_hot = hot[5]
        # make linear relationship between heating, cooling, electrical, and temperature setpoint
        cool_v_temp[i].append((cool_cold/temp_lb[i][t] + cool_hot/temp_ub[i][t])/2)
        heat_v_temp[i].append((heat_cold/temp_lb[i][t] + heat_hot/temp_ub[i][t])/2)
        elec_v_temp[i].append((elec_cold/temp_lb[i][t] + elec_hot/temp_ub[i][t])/2)
        # make linear relationship between temperature difference and cost
        cost_v_temp[i,t]=(cost_hot/temp_ub[i][t] + cost_cold/temp_lb[i][t])/2

############# load component params #################################
# sort components into their own lists and count types
class localAsset(object):
    def __init__(self,name='WSU_component', size=0, eff=1):
        self.name = name
        self.eff = eff
        self.size = size

def read_component_vertices(file_name):
    # this may need to be altered depending on signal file format
    file_b = open(file_name)
    heading = file_b.readline()
    first_vert = [float(val) for val in file_b.readline().split(", ")]
    second_vert = [float(val) for val in file_b.readline().split(", ")]
    third_vert = [float(val) for val in file_b.readline().split(", ")]
    # take the highest vertex efficiency as the linear efficiency value
    effs = [first_vert[3], second_vert[3], third_vert[3]]
    eff = max(effs)
    return eff

# make list of turbines
#gt1_eff = read_component_vertices("wsu_campus_gt1.txt")
GT1 = localAsset(name='GT1', size=2500, eff=0.34423) # at CASP
GT2 = localAsset(name='GT2', size=2187.5, eff=0.34827) # at GWSP
GT3 = localAsset(name='GT3', size=1375, eff=0.34517) # at GWSP
GT4 = localAsset(name='GT4', size=1375, eff=0.34817) # at GWSP
turbine_para = [GT1, GT2, GT3, GT4]

# make list of diesel generators
diesel_para = []

# make list of chillers
Ch1 = localAsset(name='Carrier Chiller1', size=7279.9, eff=5.874)
Ch2 = localAsset(name='York Chiller1', size=5268.245, eff=4.689)
Ch3 = localAsset(name='York Chiller3', size=5268.245, eff=4.689)
Ch4 = localAsset(name='Carrier Chiller7', size=5275.27875, eff=5.506)
Ch5 = localAsset(name='Carrier Chiller8', size=5275.27875, eff=5.506)
Ch6 = localAsset(name='Carrier Chiller2', size=4853.25645, eff=9.769)
Ch7 = localAsset(name='Carrier Chiller3', size=4853.25645, eff=9.769)
Ch8 = localAsset(name='Carrier Chiller4', size=1758.42625, eff=1.5337)
Ch9 = localAsset(name='Trane Chiller', size=1415.463, eff=4.56734)
chiller_para = [Ch1, Ch2, Ch3, Ch4, Ch5, Ch6, Ch7, Ch8, Ch9]

# make list of boilers
Boiler = localAsset(name='Boiler', size=20000, eff=0.99)
boiler_para = [Boiler, Boiler, Boiler, Boiler, Boiler]# there are 5 boilers of the same size

# make list of solar assets
rooftop_pv = localAsset(name='rooftop_pv', size=30, eff=.2)
ground_pv = localAsset(name='ground_pv', size=45, eff=.2)
renew_para = [rooftop_pv, ground_pv]

n_turb = len(turbine_para)
n_dieselgen = len(diesel_para)
n_boilers = len(boiler_para)
n_chillers = len(chiller_para)
n_renew = len(renew_para)

def find_solar_forecast(date_stamp):
    #f_ind = testdata['timestamp'].index(date_stamp)
    irrad = testdata['weather']['irrad_dire_norm']#[f_ind]
    solar_gen = sum([np.array(irrad) * (renew_para[i].size*renew_para[i].eff)/1000 for i in range(n_renew)])
    return solar_gen

renew=find_solar_forecast(timestamp)

############ load variables #########################################
var_name_list = []

#  all network objects create a group of variables associated with that object
class VariableGroup(object):
    def __init__(self, name, indexes=(), is_binary_var=False, lower_bound_func=None, upper_bound_func=None, T=T, pieces=[1]):
        global var_name_list
        self.variables = {}

        name_base = name
        #if it is a piecewise function, make the variable group be a group of arrays (1,KK)
        if pieces==[1]:
            pieces = [1 for i in indexes[0]]

        #create name base string
        for _ in range(len(indexes)):
            name_base += "_{}"

        #create variable for each timestep and each component with a corresponding name
        for index in itertools.product(*indexes):
            var_name = name_base.format(*index)

            if is_binary_var:
                var = binary_var(var_name)
            else:
                #assign upper and lower bounds for the variable
                if lower_bound_func is not None:
                    lower_bound = lower_bound_func(index)
                else:
                    lower_bound = None

                if upper_bound_func is not None:
                    upper_bound = upper_bound_func(index)
                else:
                    upper_bound = None

                #the lower bound should always be set if the upper bound is set
                if lower_bound is None and upper_bound is not None:
                    raise RuntimeError("Lower bound should not be unset while upper bound is set")

                #create the cp variable
                if lower_bound_func == constant_zero:
                    var = cvxpy.Variable(pieces[index[0]], name = var_name, nonneg=True)
                elif lower_bound is not None:
                    var = cvxpy.Variable(pieces[index[0]], name=var_name)
                    #constr = [var>=lower_bound]
                elif upper_bound is not None:
                    var = cvxpy.Variable(pieces[index[0]],name=var_name)
                    #constr = [var<=upper_bound, var>=lower_bound]
                else:
                    var = cvxpy.Variable(pieces[index[0]], name=var_name)
                

            self.variables[index] = var
            var_name_list.append(var_name)
            #self.constraints[index] = constr
        
    #internal function to find variables associated with your key
    def match(self, key):
        position = key.index(RANGE)
        def predicate(xs, ys):
            z=0
            for i, (x, y) in enumerate(zip(xs, ys)):
                if i != position and x==y:
                    z += 1
            return z == len(key)-1


        keys = list(self.variables.keys())
        keys = [k for k in keys if predicate(k,key)]
        keys.sort(key=lambda k: k[position]) 

        return [self.variables[k] for k in keys]

    #variable function to get the variables associated with the key
    def __getitem__(self, key):
        if type(key) != tuple:
            key = (key,)
    
        n_range = key.count(RANGE)

        if n_range == 0:
            return self.variables[key]
        elif n_range ==1:
            return self.match(key)
        else:
            raise ValueError("Can only get RANGE for one index.")

def constant(x):
    def _constant(*args, **kwargs):
        return x
    return _constant

constant_zero = constant(0)

# above are functions for creating and adding variables to the problem, below
# is each variable added to the problem
index_hour = (range(T),)
index_nodes = (range(1), range(T))
ep_elecfromgrid = VariableGroup("ep_elecfromgrid", indexes=index_nodes, lower_bound_func=constant_zero) #real power from grid
ep_electogrid = VariableGroup("ep_electogrid", indexes=index_nodes, lower_bound_func=constant_zero) #real power to the grid
elec_unserve = VariableGroup("elec_unserve", indexes=index_nodes, lower_bound_func=constant_zero)
if n_boilers>0:
    heat_unserve = VariableGroup("heat_unserve", indexes=index_nodes, lower_bound_func=constant_zero)
    heat_dump = VariableGroup("heat_dump", indexes=index_nodes, lower_bound_func=constant_zero)
if n_chillers>0:
    cool_unserve = VariableGroup("cool_unserve", indexes=index_nodes, lower_bound_func=constant_zero)
    #cool_dump = VariableGroup("cool_dump", indexes=index_nodes, lower_bound_func=constant_zero)

#turbines: # fuel cells are considered turbines
index_turbines = range(n_turb), range(T)
turbine_y = VariableGroup("turbine_y", indexes =index_turbines, lower_bound_func=constant_zero) #  fuel use
turbine_xp = VariableGroup("turbine_xp", indexes=index_turbines, lower_bound_func=constant_zero)  #  real power output

# diesel generators
index_dieselgen = range(n_dieselgen), range(T)
dieselgen_y = VariableGroup("dieselgen_y", indexes=index_dieselgen, lower_bound_func=constant_zero) #fuel use
dieselgen_xp = VariableGroup("dieselgen_xp", indexes=index_dieselgen, lower_bound_func=constant_zero) # real power output

#boilers:
index_boilers = range(n_boilers), range(T)
boiler_y = VariableGroup("boiler_y", indexes=index_boilers, lower_bound_func=constant_zero) #  fuel use from boiler
boiler_x = VariableGroup("boiler_x", indexes=index_boilers, lower_bound_func=constant_zero) #  heat output from boiler

#chillers
index_chiller = range(n_chillers), range(T)
chiller_x = VariableGroup("chiller_x", indexes = index_chiller, lower_bound_func = constant_zero) #  cooling power output
chiller_yp = VariableGroup("chiller_yp", indexes = index_chiller, lower_bound_func = constant_zero) #  real electric power demand

#buildingn temperatuers
index_temp = range(n_flex_buildings), range(T)
temp = VariableGroup("temp", indexes=index_temp)

################### add constraints #############################################
constraints = []

def add_constraint(name, indexes, constraint_func):
    name_base = name
    for _ in range(len(indexes)):
        name_base +="_{}"

    for index in itertools.product(*indexes):
        name = name_base.format(*index)
        c = constraint_func(index)
        constraints.append((c,name))

def electric_p_balance(index):
    i,t = index
    #sum of power
    return cvxpy.sum([turbine_xp[j,t] for j in range(n_turb)])\
    + ep_elecfromgrid[0,t] - ep_electogrid[0,t]\
    - cvxpy.sum([chiller_yp[j,t] for j in range(n_chillers)])\
    + cvxpy.sum([dieselgen_xp[j,t] for j in range(n_dieselgen)])\
    - demand['e'][t]\
    - cvxpy.sum([elec_neutral[j][t] for j in range(n_flex_buildings)])\
    - cvxpy.sum([elec_v_temp[j][t] * temp[j,t] for j in range(n_flex_buildings)])\
    + renew[t]\
    + elec_unserve[0,t] == 0

def heat_balance(index):
    i,t = index
    #sum of heat produced-heat used at this node = heat in/out of this node
    return cvxpy.sum([boiler_x[j,t] for j in range(n_boilers)])\
    + cvxpy.sum([(1-turbine_para[j].eff)*turbine_xp[j,t] for j in range(n_turb)])\
    - demand['h'][t]\
    - cvxpy.sum([heat_neutral[j][t] for j in range(n_flex_buildings)])\
    - cvxpy.sum([heat_v_temp[j][t] * temp[j,t] for j in range(n_flex_buildings)])\
    - heat_dump[0,t]\
    + heat_unserve[0,t]\
    ==0

def cool_balance(index):
    i,t  = index
    return cvxpy.sum([chiller_x[j,t] for j in range(n_chillers)])\
    + cool_unserve[0,t]\
    - demand['c'][t]\
    - cvxpy.sum([cool_neutral[j][t] for j in range(n_flex_buildings)])\
    - cvxpy.sum([cool_v_temp[j][t] *temp[j,t] for j in range(n_flex_buildings)])\
    == 0

def turbine_y_consume(index):
    i, t = index
    return turbine_xp[i,t]/turbine_para[i].eff - turbine_y[i,t] == 0

def turbine_xp_upper(index):
    i, t = index
    return turbine_xp[i,t] <= turbine_para[i].size

def dieselgen_y_consume(index):
    i, t = index
    return diesel_xp[i,t]/diesel_para[i].eff - diesel_y[i,t] == 0

def dieselgen_xp_upper(index):
    i, t = index
    return diesel_xp[i,t] <= dieselgen_para[i].size

def boiler_y_consume(index):
    i, t = index 
    return boiler_x[i,t]/boiler_para[i].eff - boiler_y[i,t] == 0

def boiler_x_upper(index):
    i, t = index
    return boiler_x[i,t] <= boiler_para[i].size

def chiller_yp_consume(index):
    i, t = index
    return chiller_x[i,t]/chiller_para[i].eff -chiller_yp[i,t] == 0

def chiller_x_upper(index):
    i, t = index
    return chiller_x[i,t] <= chiller_para[i].size

def no_slack_c(index):
    j,t = index
    return cool_unserve[j,t] == 0

def no_slack_h(index):
    j,t = index
    return heat_unserve[j,t] == 0

def no_slack_e(index):
    j,t = index
    return elec_unserve[j,t] == 0

def temperature_ub(index):
    j,t = index
    return temp[j,t] <= temp_ub[j][t]

def temperature_lb(index):
    j,t = index
    return temp[j,t] >= temp_lb[j][t]

# the functions for all constraints have been made, now add them to the problem
# add generation = demand equality constraints
add_constraint("electric_p_balance", index_nodes, electric_p_balance)
add_constraint("heat_balance", index_nodes, heat_balance)
add_constraint("cool_balance", index_nodes, cool_balance)

# add turbine constraints
index_turbine = (range(n_turb),)
add_constraint("turbine_y_consume", index_turbine + index_hour, turbine_y_consume) #False
add_constraint("turbine_xp_upper", index_turbine + index_hour, turbine_xp_upper)

# add diesel constraints
index_diesel = (range(n_dieselgen),)
add_constraint("dieselgen_y_consume", index_diesel + index_hour, dieselgen_y_consume)
add_constraint("dieselgen_xp_upper", index_diesel + index_hour, dieselgen_xp_upper)

# add boiler constraints
index_boiler = (range(n_boilers),)
add_constraint("boiler_y_consume", index_boiler + index_hour, boiler_y_consume)
add_constraint("boiler_x_upper", index_boiler + index_hour, boiler_x_upper)

#add chiller constriants
index_chiller = (range(n_chillers),)
add_constraint("chiller_yp_consume", index_chiller + index_hour, chiller_yp_consume)
add_constraint("chiller_x_upper", index_chiller + index_hour, chiller_x_upper)

if allow_thermal_slack==False:
    add_constraint("no_slack_h", index_nodes, no_slack_h)
    add_constraint("no_slack_c", index_nodes, no_slack_c)
    add_constraint("no_slack_e", index_nodes, no_slack_e)

# add building temperature constraints
add_constraint("temperature_ub", index_temp, temperature_ub)
add_constraint("temperatire_lb", index_temp, temperature_lb)

##################### add objective functions ################################

objective_components = []

# utility elec cost
for var in ep_elecfromgrid[0,RANGE]:
    objective_components.append(var * util_rate)

# gas for gas turbines
for i in range(n_turb):
    for var in turbine_y[i, RANGE]:
        objective_components.append(var * gas_rate)

# diesel for diesel generators
for i in range(n_dieselgen):
    for var in dieselgen_y[i, RANGE]:
        objective_components.append(var * diesel_rate)

# gas for boilers
for i in range(n_boilers):
    for var in boiler_y[i, RANGE]:
        objective_components.append(var * gas_rate)

# discomfort cost
for i in range(n_flex_buildings):
    for var, discomfort_cost in zip(temp[i, RANGE], cost_v_temp[i, :]):
        objective_components.append(cvxpy.abs(var) * discomfort_cost)


####################### create and solve the problem ############################

objective = cvxpy.Minimize(cvxpy.sum(objective_components))
constraints_list = [x[0] for x in constraints]
prob = cvxpy.Problem(objective, constraints_list)
print('problem created, solving problem')

tic = time.time()

result = prob.solve(solver='ECOS')

toc = time.time()-tic
print('optimal cost: '+ str(result))
print('problem solved in '+str(toc)+'seconds')

############################ save output variables to csv ##########################
filename = 'command_output_wsu.csv'
field_names = []
open_method = 'w'

with open(filename, open_method) as logfile:
    values = {}
    # go through all variables and record value
    for i in range(len(var_name_list)):
        var_name = var_name_list[i]
        split_name = var_name.split('_')
        var_name = var_name.split(split_name[-2])[0][:-1]
        j = int(split_name[-2])
        t = int(split_name[-1])
        field_name = var_name+'_'+str(j)
        # get numeric value
        var_val = eval(var_name)[j,t]
        if var_val.attributes['boolean']:
            var_val = var_val.value
        elif var_val.value == None:
            var_val = 0
        else:
            var_val = var_val.value[0]
        # add to entry
        if field_name in values:
            values[field_name].append(var_val)
        else:
            field_names.append(field_name)
            values[field_name] = [var_val]

    logger = csv.DictWriter(logfile, fieldnames = field_names, lineterminator = '\n')
    logger.writeheader()
    for t in range(T):
        values_by_row = {}
        for key, value in values.items():
            values_by_row[key] = value[t]
        logger.writerow(values_by_row)
        