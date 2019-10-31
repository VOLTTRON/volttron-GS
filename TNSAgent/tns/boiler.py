import numpy as np 

import csv
from datetime import datetime, timedelta, date, time 

from vertex import Vertex
from auction import Auction
from measurement_type import MeasurementType
from local_asset_model import LocalAssetModel
from helpers import *
from interval_value import IntervalValue

class Boiler(LocalAssetModel):
    #Boiler Class
    # The boiler interfaces with the heat auction only
    def __init__(self, name = None, size=0.0, energy_types=[MeasurementType.Heat]):
        super(Boiler, self).__init__(energy_types = energy_types)
        self.name = name
        self.activeVertices = [[] for et in energy_types]
        self.coefs = [] # dictionary of fit curves for each thermal output
        self.cost = 0.0 #float of cost to produce heat in $
        self.datafilename = None
        self.fuel = 'natural gas' # string: can be 'natural gas' or 'diesel'
        self.fuel_use = 0.0 #float indicating amount of fuel to provide heat 
        self.mass_flowrate = 0.0 #float indicating mass flow of thermal fluid through the boiler
        self.measurementType = energy_types
        self.min_capacity = 0.0 # the minimum heat output while the boiler is online in kW of heat
        self.size = size # maximum heat output in kW of heat
        self.thermalAuction = None # thermal auction the asset communicates with 
        self.thermalFluid = 'steam' # string: always steam for boiler
        self.vertices = [[] for et in energy_types] #list of Vertex class instances defining the efficiency curve

    def create_default_vertices(self, ti, mkt):
        # create the vertices that define the system generally:
        # one vertex should be at the max heat output setpoint. 
        # one vertex should be at the minimum online output setpoint
        # INPUTS:
        # 
        # OUTPUTS:
        # self.vertices: set of default vertices defining the system generally

        # start by making an efficiency fit curve
        if self.coefs == []:
            self.make_fit_curve()
        coefs = self.coefs
        max_power = self.size
        min_power = self.min_capacity
        fuel_price = 0.55907/29.3001 #price of natural gas in pullman per therm * (1/29.3001 therms/kwh)

        # The cost goes to infinity at the upper limit
        # find production price at the limit
        max_prod_cost = self.use_fit_curve(max_power)*fuel_price
        # max marginal price is infinite, because you can't go past that
        # make max vertex
        vertex_max = Vertex(marginal_price=max_prod_cost/max_power, prod_cost=max_prod_cost, power=self.size, continuity=True)
        
        # the power goes to zero at the marginal cost at the lower limit, make (0,0) vertex
        vertex_zero = Vertex(marginal_price=0.0, prod_cost=0.0, power=0.0, continuity=False)
        # find production price at the lower limit
        min_prod_cost = self.use_fit_curve(min_power)*fuel_price
        min_marginal_cost = self.use_fit_curve(min_power+1)*fuel_price-min_prod_cost
        vertex_min = Vertex(marginal_price= min_marginal_cost, prod_cost=min_prod_cost, power=self.min_capacity)
        
        for t in ti:
            # convert vertices to time intervaled values
            vmax = IntervalValue(self, t, mkt, MeasurementType.ActiveVertex, vertex_max)
            vmin = IntervalValue(self, t, mkt, MeasurementType.ActiveVertex, vertex_min)
            self.vertices[0].append(vmin)
            self.vertices[0].append(vmax)
            self.activeVertices[0].append(vmin)
            self.activeVertices[0].append(vmax)
        self.defaultVertices[0].append(vertex_min)
        self.defaultVertices[0].append(vertex_max)

        # initialize active vertices
        #self.activeVertices = self.vertices
        #self.defaultVertices = self.vertices



    def make_fit_curve(self):
        #find the vertices that describe a fit function of the power vs. heat data
        #INPUTS:
        # the fuel use and heat out are read off a csv
        #
        #OUTPUTS:
        # vertices defining cost are saved to the component

        # ASSUMPTIONS:
        # there is a csv with the same name as the boiler
        # this xlsx has entries of heat out and fuel consumed
        if self.datafilename == None:
            filename = '/efficiency_curves/'+self.name + '_efficiency.xlsx'
        else:
            filename = self.datafilename
        capacity = []
        efficiency = []
        temperature = []
        size = self.size
        # read the efficiency data, if there is no data file, return None and a warning log
        try: 
            datafile = pd.read_excel(os.getcwd()+filename)
            capacity = datafile['cap']
            efficiency = datafile['heat']
            # un-normalize the capacity data and remove (0,0) points. We don't want to fit to 0,0, because it is discontinuous
            efficiency = efficiency[capacity!=0]
            capacity = capacity[capacity!=0]
            capacity = size*capacity[efficiency!=0]
            fuel_use = 1/efficiency[efficiency!=0]*size #make this in ternms of electricity use, not efficiency
            kWhtocft = 3.41 # 3.41 cubic feet of natural gas per kWh
            # un-normalize the capacity data and remove (0,0) points. We don't want to fit to 0,0, because it is discontinuous
            capacity = size*capacity[efficiency!=0]
            fuel_use = 1/efficiency[efficiency!=0]*size*kWhtocft #make this in ternms of electricity use, not efficiency
            #bin the data according to temperature
            # n_bins = 3 # number of bins to separate sample data according to temperature
            # cap_binned, elec_binned, temp_min, temp_max = bin_data(capacity, elec_use, temperature, n_bins)
            # #save limits
            # self.fit_curve['temp_min'] = temp_min
            # self.fit_curve['temp_max'] = temp_max
            # make fit curves for each of the binned segments
            regression_order = 4 # fourth order regression should capture curve with high enough accuracy
            # for i in range(n_bins):
            #     cap = cap_binned[i]
            #     elec = cap_binned[i]
            #     coefs_binned = np.flip(np.polyfit(cap, elec, regression_order))
            #     coefs.append(coefs_binned)
            coefs = np.flip(np.polyfit(capacity, fuel_use, regression_order),0)
        except:
            coefs = [0, 1] # if there is no data start with an assumed efficiency of 1
            capacity = [0,1]
        #save values
        self.min_capacity = min(capacity)
        self.coefs = coefs

    def use_fit_curve(self, heat):
        # find the fuel use for the given power setting
        # INPUTS: coefficients for fuel use vs. power
        # power: power setpoint in kW
        # fuel_price: cost of fuel in units compatible with fit curve
        #
        # OUTPUTS: cost at power setpoint in [$/kWh]
        coefs = self.coefs
        cost = 0
        for i in range(len(coefs)):
            cost = cost + coefs[i]*heat**(i)
        #cost = cost*fuel_price
        cost = max(cost,0)
        return cost

    def update_active_vertex(self,Hsetpoint,Tamb,fuel_price, auc, ti):
        #find the vertics that are active given the heat setpoints
        #INPUTS:
        #-Hsetpoint: setpoint from auction
        #-Tamb: ambient temperature in C from weather file or agent
        #-auc.fuel_price: the market price of fuel from the auction
        #
        #OUTPUTS:
        #-activeVertices: list of active vertices for this dispatch
        #
        #update the agent's values
        self.scheduledPowers = [Hsetpoint]
        self.find_fuel_use(self,Tambient=Tamb,fuel_price=fuel_price)
        self.find_massflow(self, auc=auc)

        # use those values to create new vertices
        # calculate fuel use and fuel cost if you had to produce one more kw
        nominal_cost = self.use_fit_curve(Hsetpoint)*fuel_price
        plus_one_cost = self.use_fit_curve(Hsetpoint+1)*fuel_price
        marginal_price = plus_one_cost-nominal_cost
        #make vertex
        central_vertex = Vertex(marginal_price=marginal_price, prod_cost=nominal_cost, power=Hsetpoint)
        # put together all vertices
        active_vertices = [central_vertex, self.vertices[0].value, self.vertices[1].value]

        # update agent state
        for av in active_vertices:
            iv = IntervalValue(self, ti, mkt, MeasurementType.ActiveVertex, av)
            self.activeVertices.append(iv)

    def find_fuel_use(self, Tambient=None, fuel_price=0.55907/29.3001):
        # find the fuel use based on the setpoint and environmental temperatures
        # INPUTS:
        # - self.Hsetpoint: the heat setpoint in kW
        # - self.Treturn: the temperature of the thermal fluid into the boiler degrees C
        # - self.thermalFluid: the type of thermal fluid used for heat transfer
        # - auc.naturalGasPrice: price of fuel in $/cft (nat gas) or $/gal (diesel)
        #
        # OUTPUTS:
        # - self.fuel_use: in cubic feet if natural gas, in gallons if diesel
        # - self.cost: cost of fuel used in $

        # read in values
        Hsetpoint = self.scheduledPowers[0]
        coefs = self.coefs

        # use coefficient fit curves to find fuel use
        fuel_use = 0.0
        for i in range(len(coefs)):
            fuel_use = fuel_use + coefs * Hsetpoint ** (i)

        # save values
        self.fuel_use = fuel_use 
        self.cost = fuel_price*self.fuel_use 


    def find_massflow(self, auc):
        # find the mass flowrate required to maintain the supply and return temperatures
        # INPUTS:
        # - auction object which contains the supply and return temperatures
        # - self.Hsetpoint: heat supplied setpoint (kWh of heat)
        # - self.thermalFluid: 'steam'
        #
        # OUTPUTS:
        # - self.mass_flowrate: flowrate of thermal fluid through boiler

        Tsupply = auc.Tsupply
        Treturn = auc.Treturn
        Hsetpoint = self.scheduledPowers

        #first find specific heat at the return temperature
        Cp = 2.014 #kJ/kgK
        mfr = Hsetpoint/(Cp*(Tsupply-Treturn)) # [kg/s]
        self.mass_flowrate = mfr







