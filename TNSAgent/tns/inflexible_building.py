import numpy as np 
import pandas as pd
from datetime import datetime, timedelta, date
import os

from vertex import Vertex
from auction import Auction
from measurement_type import MeasurementType
from local_asset_model import LocalAssetModel
from helpers import *
from time_interval import TimeInterval

class InflexibleBuilding(LocalAssetModel):
    # InflexibleBuilding class describes the behavior of a building without
    # any load flexibility. The building provides loads to the thermal auctions
    # and to the electrical node with which it is associated.
    # only one vertex is ever signaled per load type
    def __init__(self, energy_types = [MeasurementType.PowerReal, MeasurementType.Heat, MeasurementType.Cooling]):
        super(InflexibleBuilding, self).__init__(energy_types=energy_types)
        self.datestamp = datetime(2010,1,1,0,0,0)
        self.dualCosts = [[] for et in energy_types]
        self.historicalProfile = None # historical load profiles from xlsx
        self.internal_mass = 1000 # mCp portion of mCp(T1-T0) equation representing building internal mass
        self.loadForecast = [0.0]*len(energy_types) # electrical load in kW
        self.mass_flowrate = [None, 0.0, 0.0] # mass flowrate of thermal fluids to meet demand
        self.measurementType = energy_types # types of energy demand
        self.name = None
        self.neighborModel = None # electrical neighbor node model
        self.thermalAuction = None
        self.thermalFluid = [None, 'steam', 'water'] # thermal fluids assocated with the energy types
        self.Tset = 23 # temperature setpoint, this setpoint is always met
        self.vertices = [] # vertices always describe infinite cost of not meeting demand


    def create_default_vertices(self, ti, mkt):
        # creaate vertices that are use on instantiation and whenever communication is lost
        # INPUTS:
        # 
        # OUTPUTS:
        # vertices: the default minimum and maximum limit vertices
        for t in ti:
            self.update_active_vertex(t, mkt)
        self.vertices = [self.activeVertices[0], self.activeVertices[1], self.activeVertices[2]]
        self.defaultVertices = [[self.activeVertices[0][0]], [self.activeVertices[1][0]], [self.activeVertices[2][0]]]
        self.defaultPower = [self.activeVertices[0][0].value.power, self.activeVertices[1][0].value.power, self.activeVertices[2][0].value.power]
    
    def update_active_vertex(self, ti, mkt):
        # update the active vertices based on the load forecast
        # INPUTS:
        # datestamp: datetime object indicating date and time for each step in horizon
        # e_cost: market price for electricity
        # h_auc: heat auction 
        # c_auc: cooling auction
        # 
        # OUTPUTS:
        # self.activeVertices_e: active vertices associated with electrical load
        # self.activeVertices_h: active vertices associated with heat load
        # self.activeVertices_c: active vertices associated with cooling load

        # update the agent's values
        self.update_load_forecast(ti)
        if MeasurementType.Heat in self.measurementType:
            self.find_massflow_steam()
        if MeasurementType.Cooling in self.measurementType:
            self.find_massflow_water()

        #read in values
        for i_energy_type in range(len(self.measurementType)):
            this_energy_type = self.measurementType[i_energy_type]
            load = self.loadForecast[i_energy_type]
            
            vertices_val = Vertex(marginal_price=float('inf'), prod_cost=float('inf'), power = -load)
            # e_load = self.loadForecast[0]
            # h_load = self.loadForecast[1]
            # c_load = self.loadForecast[2]
            # h_auc = self.thermalAuction[0]
            # c_auc = self.thermalAuction[1]
            # if h_auc.model.activeVertices[0]==[]:
            #     h_market_price = h_auc.model.marginal_price_from_vertices(h_load, h_auc.model.defaultVertices[0])
            # else:
            #     h_market_price = h_auc.model.marginal_price_from_vertices(h_load, h_auc.model.activeVertices[0])
            
            # if c_auc.model.activeVertices[0]==[]:
            #     c_market_price = c_auc.model.marginal_price_from_vertices(c_load, c_auc.model.defaultVertices[0])
            # else:
            #     c_market_price = c_auc.model.marginal_price_from_vertices(c_load, c_auc.model.activeVertices[0])

            # datestamp = self.datestamp
            
            # # inflexible buildings only bid one vertex
            # vertices_val = [[],[],[]]
            # vertices_val[0] = Vertex(marginal_price=float('inf'), prod_cost=float('inf'), power = -e_load)
            # vertices_val[1] = Vertex(marginal_price=float('inf'), prod_cost=h_market_price, power = -h_load)
            # vertices_val[2] = Vertex(marginal_price=float('inf'), prod_cost=c_market_price, power = -c_load)

            # for my_energy_type in range(len(self.measurementType)):

            iv = find_obj_by_ti(self.activeVertices[i_energy_type], ti)
            # If the active vertex does not exist, a new interval value must be
            # created and stored.
            if iv is None:
                # Create the interval value and place the active vertex in it
                iv = IntervalValue(self, ti, mkt, MeasurementType.ActiveVertex, vertices_val)
                # Append the interval value to the list of active vertices
                self.activeVertices[i_energy_type].append(iv)
            else:
                # Otherwise, simply reassign the active vertex value to the
                iv.value = vertices_val

        # self.vertices = self.activeVertices
        # self.defaultVertices = self.activeVertices
        # self.defaultVertices = self.activeVertices
        # save the active vertices
        # self.activeVertices = [[active_vertices_e], [active_vertices_h], [active_vertices_c]]

        # # if this is the initialization, create defaults
        # if self.vertices == []:
        #     self.vertices = [[active_vertices_e], [active_vertices_h], [active_vertices_c]]

    def update_load_forecast(self, ti):
        # find the historical load profiles associated with today to predict the horizon's loads
        #
        # INPUTS: 
        # - historicalProfile: load profiles with date and temperature stamps for each historical 
        #       electrical, heat, and cooling load sample point
        # - datestamp: list of datetime objects with date and time for each horizon
        #
        # OUTPUTS:
        # - loadForecast_e: electrical load profile based on historical data
        # - loadForecast_h: heat load profile based on historical data
        # - loadForecast_c: cooling load profile based on historical data
        #
        # ASSUMPTIONS:
        # there is a csv with the same name as the building object which has historical
        # load data in the format:
        # date, temperature, electric load, heat load, cooling load
        datestamp = ti.timeStamp.toordinal()-365*10-2 #self.datestamp.toordinal()

        # load historical data if you are on the first timestep
        if self.historicalProfile == None:
            try:
                filename = '/' + self.name + '.xlsx'
                datafile = pd.read_excel(os.getcwd()+filename)
            except:
                datafile = pd.read_excel(os.getcwd()+'/test_data/wsu_campus_2009_2012.xlsx')
            hist_profile = {}
            if MeasurementType.PowerReal in self.measurementType:
                e_load = datafile[self.name+'_E']
                hist_profile['e_load'] = e_load
            if MeasurementType.Heat in self.measurementType:
                h_load = datafile[self.name+'_H']
                hist_profile['h_load'] = h_load
            if MeasurementType.Cooling in self.measurementType:
                c_load = datafile[self.name+'_C']
                hist_profile['c_load'] = c_load
            hist_profile['timestamp'] = datafile['timestamp']
            self.historicalProfile = hist_profile

        # need to interpolate if dates and times don't exactly line up
        if 'e_load' in self.historicalProfile and MeasurementType.PowerReal in self.measurementType:
            i_energy_type = self.measurementType.index(MeasurementType.PowerReal)
            loadForecast_e = np.interp(datestamp, self.historicalProfile['timestamp'], self.historicalProfile['e_load'])
            self.loadForecast[i_energy_type] = loadForecast_e   
            self.defaultPower[i_energy_type] = -loadForecast_e
        if 'h_load' in self.historicalProfile and MeasurementType.Heat in self.measurementType:
            i_energy_type = self.measurementType.index(MeasurementType.Heat)
            loadForecast_h = np.interp(datestamp, self.historicalProfile['timestamp'], self.historicalProfile['h_load'])
            self.loadForecast[i_energy_type] = loadForecast_h
            self.defaultPower[i_energy_type] = -loadForecast_h
        if 'c_load' in self.historicalProfile and MeasurementType.Cooling in self.measurementType:
            i_energy_type = self.measurementType.index(MeasurementType.Cooling)
            loadForecast_c = np.interp(datestamp, self.historicalProfile['timestamp'], self.historicalProfile['c_load'])
            self.loadForecast[i_energy_type] = loadForecast_c
            self.defaultPower[i_energy_type] = -loadForecast_c
        if 'Tset' in self.historicalProfile:
            Tset = np.interp(datestamp, self.historicalProfile['timestamp'], self.historicalProfile['Tset'])
            self.Tset = Tset




    def find_massflow_steam(self):
        # find the steam massflow rate required to meet the heat load
        # INPUTS:
        # auc: heat auction object, this object contains:
        # - auc.Tsupply: temperature of steam supply loop from auction
        # - auc.Treturn: temperature of steam return loop form auction
        # loadForecast_h: heat load of building for horizon
        #
        # OUTPUTS:
        # - self.mass_flowrate[1]: the second entry in mass_flowrate is the 
        #       steam mass flowrate

        # pull values
        auc = self.thermalAuction[0]
        Tsupply = auc.Tsupply
        Treturn = auc.Treturn
        Hsetpoint = self.loadForecast[1]
        # find the specific heat of steam at the return temperature
        Cp = 2.014 #[kJ/kgK]
        # calculate the mass flowrate
        mfr = Hsetpoint/(Cp*(Tsupply-Treturn)) # [kg/s]
        self.mass_flowrate[1] = mfr

    def find_massflow_water(self):
        # find the water mass flow rate through the building required to meet
        # the cooling load given the set cooling loop return and supply temperatures
        # INPUTS:
        # auc: cooling auction objec, this object contains:
        #  - auc.Tsupply: supply temperature of cold water loop from auction
        #  - auc.Treturn: return temperature of cold water loop from auction
        # loadForecast_c: cooling load of building for horizon
        #
        # OUTPUTS:
        # - self.mass_flowrate[2]: the third entry in mass_flowrate is the 
        #       water mass flowrate through the building

        # pull values
        auc = self.thermalAuction[1]
        Tsupply = auc.Tsupply
        Treturn = auc.Treturn
        Csetpoint = self.loadForecast[2]
        # find the specific heat of water at the supply temperature
        Cp = 4.2032 #[kJ/kgK] assume pipes are not pressurized (1 atm, 4C)
        # calculate massflow
        mfr = Csetpoint/(Cp*(Treturn-Tsupply))
        # save value
        self.mass_flowrate[2] = mfr




