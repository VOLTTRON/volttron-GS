import numpy as np 
import pandas as pd
from datetime import datetime, timedelta, date
import os

from vertex import Vertex
from auction import Auction
from measurement_type import MeasurementType
from local_asset_model import LocalAssetModel
from helpers import *
from interval_value import IntervalValue

class GasTurbine(LocalAssetModel):
    # Gas Turbine class: also applies to fuel cells and diesel generators
    # the gas turbine interfaces with the heat auction and the electrical node
    def __init__(self, energy_types=[MeasurementType.PowerReal, MeasurementType.Heat]):
        super(GasTurbine, self).__init__(energy_types = energy_types)
        self.name = None
        self.activeVertices = [[] for et in energy_types]# active vertices that are sent to electric node
        self.cost = 0.0
        self.datafilename = None
        self.engagementSchedule = [[] for et in energy_types]
        self.fit_curve = {}# fit curve parameters to relate electricity generated, fuel used, and max heat recoverable
        self.fuel = 'natural gas'
        self.fuel_use = 0.0 # amount of natural gas consumed to meet setpoint in cft
        self.mass_flowrate = 0.0 # the mass flowrate of steam through the heat recovery system
        self.max_heat_recovered = 0.0 # amount of heat recovered without incuring additional cost from ramping up gas turbine
        self.measurementType = energy_types
        self.min_capacity = 0.0 # minimum capacity setpoint when online as a fraction (0.1 = 10%)
        self.neighborModel = None # electrical neighbor node model
        self.size = 0.0 # maximum electrical power output of CHP generator
        self.thermalAuction = None # thermal auction which this asset communicates
        self.thermalFluid = 'steam' # CHP gas turbines reject waste heat to steam for heat recovery
        self.vertices = [[] for et in energy_types]# vertices that define the capacity vs. fuel use of the CHP
         

    def create_default_vertices(self, ti, mkt):
        # create the vertices that define the system generally:
        # one vertex should be at the max heat output setpoint. 
        # one vertex should be at the minimum online output setpoint
        # INPUTS:
        # 
        # OUTPUTS:
        # self.vertices: set of default vertices defining the system generally

        # start by making an efficiency fit curve
        if self.fit_curve == {}:
            self.make_fit_curve()
        coefs = self.fit_curve['coefs_e']
        max_power = self.size
        min_power = self.min_capacity
        fuel_price = 0.55907/29.3001 #price of natural gas in pullman per therm * (1/29.3001 therms/kwh)

        # The cost goes to infinity at the upper limit
        # find production price at the limit
        max_prod_cost = self.use_fit_curve(coefs, max_power, fuel_price)
        # find marginal price by taking difference for price just below limit
        max_marginal_cost = max_prod_cost/self.size#self.use_fit_curve(coefs, max_power+1, fuel_price)-max_prod_cost
        # make max vertex
        vertex_max = Vertex(marginal_price=max_marginal_cost, prod_cost=max_prod_cost, power=self.size, continuity=True)
        heat_v_max = Vertex(marginal_price=0.01, prod_cost=self.size*0.6*0.01, power=self.size*0.6, continuity=True)
            
        # the power goes to zero at the marginal cost at the lower limit, make (0,0) vertex
        vertex_zero = Vertex(marginal_price=0.0, prod_cost=0.0, power=0.0, continuity=False)
        # find production price at the lower limit
        min_prod_cost = self.use_fit_curve(coefs, min_power, fuel_price)
        min_marginal_cost = self.use_fit_curve(coefs, min_power+1, fuel_price)-min_prod_cost-0.001
        vertex_min = Vertex(marginal_price= min_marginal_cost, prod_cost=min_prod_cost, power=self.min_capacity)
        heat_v_min = Vertex(marginal_price= 0.0, prod_cost=0.0, power=self.min_capacity*0.6)

        for t in ti:
            vertex_max_i = IntervalValue(self, t, mkt, MeasurementType.ActiveVertex, vertex_max)
            vertex_min_i = IntervalValue(self, t, mkt, MeasurementType.ActiveVertex, vertex_min)
            heat_v_max_i = IntervalValue(self, t, mkt, MeasurementType.ActiveVertex, heat_v_max)
            heat_v_min_i = IntervalValue(self, t, mkt, MeasurementType.ActiveVertex, heat_v_min)

            #save values
            self.activeVertices[0].append(vertex_min_i)
            self.activeVertices[0].append(vertex_max_i)
            self.activeVertices[1].append(heat_v_min_i)
            self.activeVertices[1].append(heat_v_max_i)

        self.vertices =  [self.activeVertices[0], self.activeVertices[1]]
        self.defaultVertices = [[self.activeVertices[0][0]],[self.activeVertices[1][0]]]
        self.defaultPower = [self.activeVertices[0][0].value.power, self.activeVertices[1][0].value.power]
        #self.scheduledPowers = [[IntervalValue(self, ti[0], mkt, MeasurementType.ScheduledPower, self.min_capacity)],[IntervalValue(self, ti[0], mkt, MeasurementType.ScheduledPower, self.min_capacity*0.6)]]

    def make_fit_curve(self):
        #find the coefficients that describe a fit function of the fuel use vs. electric generation and max heat recoverable
        # This function should be run once after object initialization, and again whenever
        # efficiency fit data is updated for the most accurate efficiency fit curve
        #INPUTS:
        # the electric generation, fuel use, heat recovery and inlet temperature are read off a csv
        #
        #OUTPUTS:
        # component fit curves and temperature ranges which apply to those curves are saved to the component

        # ASSUMPTIONS:
        # there is a csv with the same name as the boiler
        # this csv has entries of heat out and fuel consumed

        filename = self.name + '_efficiency.xlsx'
        capacity = []
        fuel_use = []
        heat_recovered = []
        temperature = []
        coefs_e = []
        coefs_h = []
        size = self.size
        # read the efficiency data, if there is no data file, return None and a warning log
        try: 
            datafile = pd.read_excel(os.getcwd()+'/efficiency_curves/'+filename)
            capacity = datafile['cap']
            efficiency = datafile['elec']
            heat_recovered = datafile['heat']
            # remove zero capacity reading
            efficiency = efficiency[capacity!=0]
            heat_recovered = heat_recovered[capacity!=0]
            capacity = capacity[capacity!=0]
            kWhtocft = 3.41 # 3.41 cubic feet of natural gas per kWh
            # convert efficiency to fuel use
            fuel_use = 1/efficiency*capacity*size*kWhtocft #convert to cubic feet of natural gas 
            # un-normalize the capacity data and remove (0,0) points. We don't want to fit to 0,0, because it is discontinuous
            capacity = size*capacity[fuel_use!=0]
            self.min_capacity = min(capacity)
            fuel_use = fuel_use[fuel_use!=0]
            heat_recovered = heat_recovered[fuel_use!=0]*capacity

            # temperature = temperature[fuel_use!=0]
            #bin the data according to temperature
            # n_bins = 3 # number of bins to separate sample data according to temperature
            # cap_binned, fuel_binned, temp_min, temp_max = bin_data(capacity, fuel_use, temperature, n_bins)
            # _, heat_binned, _, _ = bin_data(capacity, heat_recovered, temperature, n_bins) # the bins should be the same
            # #save limits
            # self.fit_curve['temp_min'] = temp_min
            # self.fit_curve['temp_max'] = temp_max
            # make fit curves for each of the binned segments
            # regression_order = 4 # fourth order regression should capture curve with high enough accuracy
            # for i in range(n_bins):
            #     cap = cap_binned[i]
            #     fuel = fuel_binned[i]
            #     heat = heat_binned[i]
            #     coefs_e_binned = np.flip(np.polyfit(cap, fuel, regression_order))
            #     coefs_h_binned = np.flip(np.polyfit(heat, cap, 2))
            #     coefs_e.append(coefs_e_binned)
            #     coefs_h.append(coefs_h_binned)
            regression_order = 4 # fourth oder regression should capture curve with high enough accuracy
            coefs_e = np.flip(np.polyfit(capacity, fuel_use, regression_order),0)
            coefs_h = np.flip(np.polyfit(heat_recovered, fuel_use, regression_order),0)
        except:
            coefs_e = [0, 2] # if there is no data start with an assumed efficiency of 50%
            coefs_h = [0, 1/2] # if there is no data start with an assumed waste heat 2* power out
        #save values
        self.fit_curve['coefs_e'] = coefs_e
        self.fit_curve['coefs_h'] = coefs_h

    def use_fit_curve(self, coefs, power):
        # find the fuel use for the given power setting
        # INPUTS: 
        # coefs: coefficients for fuel use vs. power
        # power: power setpoint in kW
        # fuel_price: cost of fuel in units compatible with fit curve
        #
        # OUTPUTS: cost at power setpoint in [$/kWh], or electric needed for that amount of heat
        #coefs = self.fit_curve['coefs_e']
        cost = 0
        for i in range(len(coefs)):
            cost = cost + coefs[i]*power**(i)
        # cost = cost*fuel_price
        cost = max(cost,0)
        return cost

    def update_active_vertex(self, Esetpoint, Hsetpoint, Tamb, e_cost, h_cost, fuel_price, ti, mkt):
        # find the electrical and heating vertices that are active given the heat and 
        # electrical setpoints
        # INPUTS:
        # - Esetpoint: setpoint from electric node
        # - Hsetpoint: setpoint from auction
        # - e_cost: electricity market price from meighbor model
        # - h_cost: heat market price from auction
        #
        # OUTPUTS:
        # - activeVertices_e: list of active vertices for this dispatch associated with the electrical market
        # - activeVertices_h: list of active vertices for this dispatch associated with the heat auction

        # update the agent's values
        #self.scheduledPowers = [Esetpoint, Hsetpoint]
        self.Hsetpoint = Hsetpoint
        self.find_max_heatrecovered(self)
        self.find_massflow(self)
        active_vertices_e = []
        active_vertices_h = []

        #read in values
        coefs_e = self.fit_curve['coefs_e']
        coefs_h = self.fit_curve['coefs_h']


        # use those values to create new vertices
        # there shuold be one vertex at (0,0), 
        # if the electrical setpoint is above zero there should be
        # one vertex at the lower bound with fuel cost only associated with electrical use
        # one vertex at the electrical setpoint with fuel cost only assocated with electrical use
        # one vertex at the max_heat(electrical_setpoint) with cost only associated with heat
        # one vertex at the max heat recovery setpoint with cost only assocaited with heat
        #
        # make the vertex at the electrical setpoint
        cost_dn_e = self.use_fit_curve(power = Esetpoint, fuel_price=fuel_price, coefs=coefs_e)
        cost_up_e = self.use_fit_curve(power=Esetpoint+1, fuel_price=fuel_price, coefs=coefs_e)
        marginal_eset = cost_up_e-cost_dn_e
        e_setpoint_vertex = Vertex(marginal_price=marginal_eset, prod_cost=cost_dn_e, power = Esetpoint)
        
        # find the marginal price at the lower bound of the generator online
        lb_cost = self.use_fit_curve(power=self.min_capacity, fuel_price=fuel_price, coefs=coefs_e)
        lb_cost_up = self.use_fit_curve(power=self.min_capacity, fuel_price=fuel_price, coefs=coefs_e)
        lb_marginal = lb_cost_up-lb_cost

        # find the marginal price at the upper bound of the generator
        ub_cost = self.use_fit_curve(power=self.size, fuel_price=fuel_price, coefs=coefs_e)
        heat_ub = self.find_max_heatrecovered(e_setpoint=self.size)
        ub_marginal = float('inf') # the marginal price is infinite because you can't go above this
        
        # make the zero cost vertex for heat less than what you can recover
        # heat incurst no cost until it is above what is produced by waste
        # find out the heat you can recover from this electric setpoint
        max_heat_recovered = self.find_max_heatrecovered()
        #find the lower bound output in terms of heat
        heat_lb = self.use_fit_curve(power=self.min_capacity, fuel_price=1, coefs=coefs_h)
        #make the vertex such that that amount of heat has no cost if you are already using it for electricity
        if Esetpoint>self.min_capacity:
            # find lower bound vertices and assign all cost to electric
            heat_lb_vertex = Vertex(marginal_price=0.0, prod_cost=0.0, power=heat_lb)
            elec_lb_vertex = Vertex(marginal_price=lb_marginal, prod_cost=lb_cost, power=self.min_capacity)
            
            # find mid vertices
            heat_mid_vertex = Vertex(marginal_price=0.0, prod_cost=0.0, power=self.max_heat_recovered)
            elec_mid_vertex = e_setpoint_vertex

            # assign vertices for the upper bound
            heat_ub_vertex = Vertex(marginal_price=float('inf'), prod_cost=0.0, power=heat_ub)
            elec_ub_vertex = Vertex(marginal_price=float('inf'), prod_cost=ub_cost, power=self.size)

            # find second mid vertex:
            # if the heat required is more than what can be recovered, make another vertex to assign cost to heat
            # if the heat required is less than what can be recovered, leave cost with electric
            if Hsetpoint> max_heat_recovered:
                capacity_Hsetpoint = self.use_fit_curve(power=Hsetpoint, fuel_price=1, coefs = coefs_h)
                # check to see if that setpoint is possible
                if capacity_Hsetpoint > self.size:
                    capacity_Hsetpoint = self.size
                    Hsetpoint=heat_ub
                # find the marginal cost of outputting at that capacity
                capacity_Hsetpoint_up = self.use_fit_curve(power=Hsetpoint+1, fuel_price=1, coefs=coefs_h)
                cost_dn_h = self.use_fit_curve(power=capacity_Hsetpoint, fuel_price=fuel_price, coefs=coefs_e)
                cost_up_h = self.use_fit_curve(power=capacity_Hsetpoint_up, fuel_price=fuel_price, coefs=coefs_e)
                marginal_hset = cost_up_h-cost_dn_h
                # make vertices at this marginal cost
                heat_set_vertex = Vertex(marginal_price=marginal_hset, prod_cost=cost_dn_h-cost_dn_e, power=Hsetpoint)
                elec_set_vertex = Vertex(marginal_price=0.0, prod_cost=cost_dn_e, power=capacity_Hsetpoint)
                
                # adjust the upper bound vertices to split the cost between electric and heat
                heat_ub_vertex = Vertex(marginal_price=float('inf'), prod_cost=ub_cost-cost_dn_e, power=heat_ub)
                elec_ub_vertex = Vertex(marginal_price=float('inf'), prod_cost=cost_dn_e, power=self.size)
                
            active_vertices_h = [heat_set_vertex, heat_lb_vertex, heat_mid_vertex, heat_ub_vertex]
            active_vertices_e = [elec_set_vertex, elec_lb_vertex, elec_mid_vertex, elec_ub_vertex]
        # otherwise this incurs a cost, because you aren't already producing for electricity
        else:
            #use the marginal price at the lower bound and apply it to only heat
            heat_lb_vertex = Vertex(marginal_price=lb_marginal, prod_cost=lb_cost, power=heat_lb)
            # if the electric setpoint is zero, create a vertex with zero cost of electric, because all costs are incured by heat
            elec_lb_vertex = Vertex(marginal_price=0.0, prod_cost=0.0, power = self.min_capacity)
            
            # if the heat setpoint is above zero, assign cost for heat only
            if Hsetpoint>0: 
                heat_ub_vertex = Vertex(marginal_price=float('inf'), prod_cost=ub_cost, power=heat_ub)
                elec_ub_vertex = Vertex(marginal_price=float('inf'), prod_cost = 0.0, power=self.size)

            active_vertices_h = [heat_lb_vertex, heat_ub_vertex]
            active_vertices_e = [e_setpoint_vertex, elec_lb_vertex, elec_ub_vertex]
        
        active_vertices_e = [IntervalValue(self, ti, mkt, MeasurementType.ActiveVertex, vert) for vert in active_vertices_e]
        active_vertices_h = [IntervalValue(self, ti, mkt, MeasurementType.ActiveVertex, vert) for vert in active_vertices_h]

        # update agent state
        self.activeVertices = [[active_vertices_e],[active_vertices_h]]


    def find_max_heatrecovered(self, e_setpoint=None):
        # the heat recovered is limited by the generator setpoint. If more waste heat is desired than 
        # this limit, the generator must ramp up incuring a cost. Less heat however, may not incur a lower cost
        # if it is still valuable to produce electricity.
        # INPUTS:
        # - self.Esetpoint: generator electricity setpoint
        # - self.coefs_h: heat fit curve coefficients where e_set = f(coefs_h, heat_set), these are second order
        #
        # OUTPUTS:
        # - max_heat_recovered: maximum amount of heat that can be recovered without incurring additional
        #       from ramping up the gas turbine

        #read in inputs
        if e_setpoint == None:
            e_setpoint = self.scheduledPowers[0][0].value.power
        max_heat_recovered = 0.0
        coefs_h = self.fit_curve['coefs_h']
        # use quadratic formula
        max_heat_recovered = (-coefs_h[1] + np.sqrt(coefs_h[1]**2-4*coefs_h[0]*coefs_h[2]) )/(2*coefs_h[0])
        # if it's negative try the other one
        if max_heat_recovered<0:
            max_heat_recovered = (-coefs_h[1] - np.sqrt(coefs_h[1]**2-4*coefs_h[0]*coefs_h[2]) )/(2*coefs_h[0])
        # if it's still negative, say it's zero
        if max_heat_recovered<0:
            max_heat_recovered = 0.0

        # return value
        return max_heat_recovered


    def find_massflow(self, auc):
        # find the mass flowrate of steam through the heat recovery system to meet the 
        # heat setpoint with the network supply and return temperatures
        # INPUTS:
        # - auc.Tsupply: temperature of steam supply loop from the auction object
        # - auc.Treturn: temperature of steam return loop from the auction object
        # - Hsetpoint: heat supply setpoint in kW
        #
        # OUTPUTS:
        # - self.mass_flowrate: the mass flowrate of steam through the heat recovery system in kg/s

        # pull values
        Tsupply = auc.Tsupply
        Treturn = auc.Treturn
        Hsetpoint = self.Hsetpoint
        # find specific heat at steam return temperature
        Cp = 2.014 #kJ/kgK
        # calculate mass flowrate
        mfr = Hsetpoint/(Cp*(Tsupply-Treturn)) # [kg/s]
        self.mass_flowrate = mfr