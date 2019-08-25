import numpy as np 
import csv
from datetime import datetime, timedelta, date

from thermal_agent_model import ThermalAgentModel 
from vertex import Vertex
from auction import Auction
from measurement_type import MeasurementType
from local_asset_model import LocalAssetModel
import pulp

class ColdEnergyStorage(LocalAssetModel):
    # cold thermal energy storage tank
    # the thermal storage tank is on the cold water loop
    # supply and return water do not mix
    # when charging the tank fills with cold water and sends warm water to the return
    # when discharging the tank fills with return water and sends cold water to the supply
    # the tank does not submit bids with costs, it only submits its
    # effective load on the cooling distribution system based on the cold
    def __init__(self,name=None, size=10000, measurementType=MeasurementType.Cooling):
        super(ColdEnergyStorage, self).__init__()
        self.Csetpoint = None # cooling power setpoint as self-determined based on the cooling auction prices
        self.electrical_power_draw = [0.0] # this feature will be implemented later
        self.mass_flowrate = None # mass flowrate of cold water out of the tank
        self.mass_stored_cold_water = [size/2] # cold energy state of charge in the form of kg of cold water stored
        self.measurementType = measurementType
        self.name = name
        self.size = size # cold water stored in kWh of cooling
        self.ramp_rate = size # ramp rate for these types is very fast
        self.thermalAuction = None # cooling auction associated with cold thermal storage

    def update_active_vertices(self):
        # update the active vertices to reflect the projected cooling power dispatch
        # of the cold water tank
        # INPUTS:
        # - auc.marginalPrices: projected marginal prices of cooling power for the horizon
        # - mass_stored_cold_water[0]: initial condition of cold water stored in tank
        #
        # OUTPUTS:
        # - activeVertices: vertices describing the cooling power discharge (negative indicates charging) 
        #       of the tank over the horizon

        # read in inputs
        auc = self.thermalAuction
        marginalPrices = auc.marginalPrices
        if marginalPrices == []:
            marginalPrices = auc.defaultPrice
            
        # potentially need active vertices to also know demand?
        # auction_vertices = auc.activeVertices
        mass_init = self.mass_stored_cold_water[0]

        # optimize over the horizon
        self.optimize_storage_use()

        # use setpoint to create vertices
        activeVertices = [Vertex(marginal_price=float('inf'), prod_cost=0.0, power=self.Csetpoint)]

        # save vertices
        self.activeVertices = activeVertices

    def find_mass_flowrate(self, auc):
        # find the mass flowrate of cold water into the tank and the mass
        # also find the mass of cold water stored in the tank which represents the state of charge
        # INPUTS:
        # - Csetpoint: cooling power setpoint for cold water tank
        # - mass_stored_cold_water: initial guess of mass stored in the tank at each timestep
        # - auc.Tsupply: supply temperature of water from cold water loop
        # - auc.Treturn: return temperature of water to cold water loop
        # 
        # OUTPUTS:
        # - mass_stored_cold_water: mass of stored cold water in the tank for each timestep in kg
        # - mass_flowrate: flowrate of cold water out of the tank (can be negative) to reach cold setpoint 

        # pull values
        Csetpoint = self.Csetpoint # positive indicates discharging
        SOC = self.mass_stored_cold_water #state of charge representation
        Tsupply = auc.Tsupply
        Treturn = auc.Treturn

        # find specific heat of water at supply temperature
        Cp = 4.2032 # [kJ/kg K]
        # find massflowrate of cold water out of the tank
        mfr = Csetpoint/(Cp * (Treturn-Tsupply))
        # find change in mass stored in tank
        # this is dependent on the previous state of charge so do it sequentially
        # start with initial condition
        SOC[0] = SOC[0]-mfr[0]
        for t in range(1,len(mfr)):
            # state of charge gets updated, initial values are from previous horizon
            SOC[t] = SOC[t-1] - mfr[t]
        # the mass flowrate of return water into the tank is equal to the mass
        # flowrate of cold water out of the tank
        mfr_return = mfr

        #save values
        self.mass_stored_cold_water = SOC
        self.mass_flowrate = mfr

    def find_electrical_pump_power(self):
        # find the pump power required to meet the cold water mass flowrate
        # this function can be defined later
        # INPUTS:
        # - mass_flowrate: flowrate of cold water into the tank in kg/s
        # 
        # OUTPUTS:
        # - electrical_power_draw: electrical power to the pump in kW
        pass

    def find_skin_losses(self, Tamb):
        # find the thermal losses through the skin of the tank
        # this function can be defined later
        # INPUTS:
        # self.mass_stored_cold_water: the mass of cold water in tank as a representation of state of charge
        # Tamb: ambient temperature in degrees C
        # 
        # OUTPUTS:
        # self.mass_stored_cold_water: reduce the mass of cold water in the tank by a small amount
        #       to simulate skin losses

        # read inputs
        SOC = self.mass_stored_cold_water
        T_tank = 4 # [degrees C] tank internal cold water temperature

        #calculate skin losses
        #assume tank is 1/2 inch fiber glass 
        K_fiberglass = 0.04 #[W/mk] conductivity of fiberglass
        K_tank = K_fiberglass*(0.25)*(0.0254) # conductivity * thickness * inches to meters
        # assume the air is at an ambient temperature of about 27 C and find convection coefficient
        # calculate the convection coefficient of air
        # use vertical flat plate in convection model:
        # Rayleigh number:
        g = 9.81 # [m/s^2] gravity constant
        beta = 1
        L_characteristic = 5 # [m] characteristic length (height of tank)
        nu = 1
        alpha = 1
        T_surface_estimate = 20 + 273 # [K] estimate of surface temp in Kelvin to get the Rayleigh number
        Ra = (g*beta*(T_surface_estimate-Tamb)*L_characteristic**3)/(nu*alpha)
        # find nusselt number
        Nu = (0.825 + (0.387*Ra**(1/6)/(1+(0.492/Pr)**(9/16))**(8/27))**2)
        # find convection coefficient
        K_air = .0263 #[W/mK] conduction coefficient of air
    
    def optimize_storage_use(self):
        # based on the projected marginal prices for the horizon, find
        # an optimal dispatch of the energy storage
        # INPUTS:
        # - auc.vertices: cooling prices and net loads over the horizon
        # - self.SOC[0]: initial condition of mass of cold water in the tank
        #
        # OUTPUTS:
        # - Csetpoint: cooling power setpoint for energy storage
        #
        # METHOD:
        # use a mixed integer linear solver to find the optimal energy storage dispatch

        # read in values
        auc = self.thermalAuction
        vertices = auc.activeVertices[0]
        T = auc.intervalsToClear # the number of timesteps 
        mass_init = self.mass_stored_cold_water[0] # initial condition of cold water mass stored in tank [kg]
        # convert vertices to marginal price and power demand
        demand = []
        marginal_price = []
        if vertices == []:
            marginal_price = [auc.defaultPrice]*T
            demand = [0]*T
        else:
            for vert in vertices:
                demand.append(vert.power)
                marginal_price.append(vert.marginalPrice)
        # find the mean marginal price to attribute value for energy stored at the last timestep
        mean_marginal_price = np.mean(marginal_price)    

        # setup problem
        prob = pulp.LpProblem("storage optimization", pulp.LpMinimize)
        # variable is state of charge
        soc = []
        for t in range(T+1):
            soc_name = 'soc_'+str(t)
            soc_i = pulp.LpVariable(soc_name, lowBound=0, upBound=self.size, cat='Continuous')
            soc.append(soc_i)
        # objective function is the marginal cost times the power delivered
        # the sum of the price to meet demand minus value of residual stored energy
        for i in range(T):
            prob += marginal_price[i] * (demand[i] + soc[i+1]-soc[i]), "cooling cost {}".format(i)
        prob += mean_marginal_price * soc[-1], "residual stored energy"
        # constraint 0 is that the initial condition state of charge is soc[0]
        #prob += soc[0] == self.mass_stored_cold_water
        # constraint 1 is that ramp rates are adhered to
        for t in range(1,T+1):
            prob += soc[t]-soc[t-1] <= self.ramp_rate
            prob += soc[t-t]-soc[t] <= self.ramp_rate

        # optimize
        prob. solve()

        # sort solution
        soc_values = []
        for var in prob.variables():
            soc_values.append(var.varValue)
        # the cooling set points are the difference in state of charge
        self.state_of_charge = soc_values[1]
        Csetpoint = []
        for t in range(1,T+1):
            Csetpoint.append(soc_values[t]-soc_values[t-1])

        # save value
        self.Csetpoint = Csetpoint

    