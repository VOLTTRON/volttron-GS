from datetime import datetime, timedelta, date, time
import csv

import logging
#utils.setup_logging()
_log = logging.getLogger(__name__)

from model import Model
from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from interval_value import IntervalValue
from transactive_record import TransactiveRecord
from meter_point import MeterPoint
from market import Market
from time_interval import TimeInterval
from neighbor import Neighbor
from neighbor_model import NeighborModel
from local_asset import LocalAsset
from local_asset_model import LocalAssetModel
from myTransactiveNode import myTransactiveNode

class ThermalAgentModel(Model, object):
    # ThermalAgentModel class
    # The ThermalAgent manages the interface with an auction or node and 
    # represents it for the computational agent
    # Members of the transactive network must be indicated by setting the
    # "transactive" property true.

    def __init__(self):
        self.converged = False
        self.convergenceFlags = [] # IntervalValue.empty # values are Boolean
        self.convergenceThreshold = 0.01 #[0.01 to 1#]
        self.demandMonth = datetime.today().month # used to re-set demand charges
        self.demandRate = 10 # [$/kW (/h)]
        self.demandThreshold = 1e9 # power that causes demand charges [kW]
        self.effectiveImpedance = 0.0 # Ohms for future use
        self.friend = False # friendly neighbors might get preferred rates
        self.mySignal = [] # TransactiveRecord.empty # current records ready to send
        self.receivedSignal = [] # TransactiveRecord.empty # last records received
        # NOTE: sentSignal is deeded as part of event-driven timing of the system.
        # it allows a comparison between a recent calculation (mySignal) and the last
        # calculation that was revealed to the Neighbor (sentSignal).
        self.sentSignal = [] # TransactiveRecord.empty # last records sent
        self.transactive = False
        #self.energy_type = ['heat', 'electrical'] # list of strings indicating 'heat', 'cooling', and or 'electric' type thermal energy
        self.thermalFluid = 'steam' # string representing 'steam' or 'water' used to transfer energy

    # any function is done for each energy type: i.e. if the component is a CHP generator, it would 
    # have self.energy_type = ['heat', 'electrical'] and if one were to call 'calculate_reserve_margin'
    # it would be done once for heat and once for electrical

    def calculate_reserve_margin(self, mkt):
        # CALCULATE_RESERVE_MARGIN() - Estimate the spinning reserve margin in each active time interval
        # 
        # Reserve margin is defined here as additional generation or reduced consumption
        # above the currently scheduled power. The intention is for this to represent "spinning-reserve"
        # power that can be available on short notice
        # 
        # For now, this quantity will be tracked. In the future, treatment of resource commitment
        # may allow meaningful control of reserve margin and the resiliency it supports
        #
        # ASSUMPTIONS:
        # - time intervals are up-to-date
        # - scheduled power is up-to-date
        # - the active vertices are up-to-date and correct. One of the vertices
        # represents the maximum power that is available on short notice (i.e., "spinning reserve")
        # from this thermal agent
        #
        #INPUTS:
        # obj - thermal agent model
        # mkt - market object

        # gather active time intervals ti
        time_intervals = mkt.timeIntervals

        # index through active time intervals ti
        for i in range(len(time_intervals)): 
            #find the max available power from among the active vertices
            # in the indexed time interval, one of which must represent
            # maximum power
            maximum_power = find_objs_by_ti(self.activeVertices, time_intervals[i])
            if len(maximum_power) == 0:
                # no active vertex was found the hard constraint must be used
                maximum_power = self.object.maximum_power
            else:
                maximum_power = [x.value for x in maximum_power]
                maximum_power = [x.power for x in maximum_power]
                maximum_power = max(maximum_power)
            #make sure the operational max does not exceed the physical constraint
            maximum_power = min(maximum_power, self.object.maximumPower)

        # find scheduled power for this asset in the indexed time interval
        scheduled_power = find_obj_by_ti(self.sheduledPowers, time_interval[i])
        scheduled_power = scheduled_power.value

        # the available reserve margin is calculated as the difference between the maximum and scheduled powers
        # make sure the value is not less than zero
        value = max(0, maximum_power-scheduled_power) # reserve margin [avg. kW]

        # update reserve margin value
        interval_value = find_obj_by_ti(self.reserveMargins, time_interval[i])
        if interval_value is None:
            interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ReserveMargin, value)
            self.reserveMargins.append(interval_value)
        else:
            interval_value.value = value #[avg. kW]


    def prep_transactive_signal(self, mkt):
        # PREP_TRANSACTIVE_SIGNAL() - Prepare transactive records to send
        # to a transactive neighbor. The prepared transactive signal should 
        # represent the residual flexibility and cost
        #
        # INPUTS:
        # obj - thermal agent model
        # mkt - market object
        # 
        # OUTPUTS:
        # - Updates mySignal property, which contains transactive records that are ready
        # to send to the transactive neighbor
        
        # gather active time intervals
        time_intervals = mkt.timeIntervals # active Time Interval objects

        #index through active time intervals
        for i in range(len(time_intervals)):
            #keep only transactive records that are not in the indexed time interval
            self.mySignal = [x for x in self.mySignal if x.timeInterval != time_intervals[i].name]
 
            vertex_powers = [x.power for x in self.activeVertices]

            maximum_vertex_power = max(vertex_powers) # [avg. kW]
            minimum_vertex_power = min(vertex_powers) # [avg. kW]

            #marginal price on curve that corresponds to minimum power
            marginal_price_1 = self.marginal_price_from_vertices(minimum_power, vertices)
            marginal_price_2 = self.marginal_price_from_vertices(maximum_power, vertices)

            #create a transactive record: record #1 = minimum power
            # record #2 = maximum power
            transactive_record = TransactiveRecord(time_intervals[i], 1, marginal_price_1, minimum_vertex_power)
            self.mySignal.append(transactive_record)
            transactive_record = TransactiveRecord(time_intervals[i], 2, marginal_price_2, maximum_vertex_power)
            self.mySignal.append(transactive_record)

        # if self.electricalComponent:
        #     e_transactive_record = TransactiveRecord(time_intervals, index, marginal_price, power)
        

    def receive_transactive_signal(self, mtn):
        # FUNCTION RECEIVE_TRANSACTIVE_SIGNAL() - receive and save transactive records from node
        
        #make a text file of the transactive signal
        #shorten the name or this node and the target node to format the file name
        source_node = str(self.object.name)
        if len(source_node) > 5:
            source_node = source_node[0:5]

        target_node = str(mtn.name)
        if len(targe_node)>5:
            target_node = target_node[0:5]
        filename = ''.join([source_node,'-', target_node, '.txt'])
        filename = filename.replace(' ', '')

        #read signal, which is a csv record
        with open(filename) as file:
            reader = csv.DictReader(file)
            # Extract the interval information into transactive records.
            # NOTE: A TransactiveRecord constructor is being used.
            for row in reader:  # for i = 1:r
                transative_record = TransactiveRecord(ti=row['TimeInterval'],
                                                      rn=int(row['Record']),
                                                      mp=float(row['MarginalPrice']),
                                                      p=float(row['Power']),
                                                      pu=float(row['PowerUncertainty']),
                                                      cost=float(row['Cost']),
                                                      rp=float(row['ReactivePower']),
                                                      rpu=float(row['ReactivePowerUncertainty']),
                                                      v=float(row['Voltage']),
                                                      vu=float(row['VoltageUncertainty']))
                #save each row as a signal
                self.receivedSignal.append(transactive_record)


    def send_transactive_signal(self, auc):
        # SEND_TRANSACTIVE_SIGNAL() - send transactive records to a transactive
        # auction.
        #
        # Retrieves the current transactive records, formats them into a table, and
        # "sends" them to a text file for the auction. The property
        # mySignal is a storage location for the current transactive records, which
        # should capture at least the active time intervals' local marginal prices
        # and the power that is scheduled to be received from or sent to the
        # neighbor.
        # Records can also capture flex vertices for this neighbor, which are the
        # supply or demand curve, less any contribution from the neighbor.
        # Transactive record #0 is the scheduled power, and other record numbers
        # are flex vertices. This approach anticipates that transactive signal
        # might not include all time intervals or replace all records. The neighbor
        # similarly prepares and sends transactive signals to this location.
        # obj - AssetModel object
        # auc - Auction object

        # Collect current transactive records concerning this asset
        tr = self.mySignal
        tr_len = len(tr) #number of records in signal

        if tr_len == 0:
            _log.warning("No transactive records were found. No transactive signal can be sent to %s." % self.name)
            return

        # send the signal
        # generate a meaningful filename from source node name and target node name
        source_node = str(auc.name)
        if len(source_node) > 5:
            source_node = source_node[0:5]

        target_node = str(self.object.name)
        if len(target_node) > 5:
            target_node = target_node[0:5]

        filename = join([source_node, '-', target_node, '.txt.'])
        filename = filename.replace(' ', '')

        # write the table
        lines =  [
            "TimeStamp,TimeInterval,Record,MarginalPrice,Power,PowerUncertainty,Cost,ReactivePower,ReactivePowerUncertainty,Voltage,VoltageUncertainty"
        ]
        for i in range(tr_len):  # for i = 1:len
            lines.append(','.join([
                str(tr[i].timeStamp),
                str(tr[i].timeInterval),
                str(tr[i].record),
                str(tr[i].marginalPrice),
                str(tr[i].cost),
                str(tr[i].power),
                str(tr[i].powerUncertainty),
                str(tr[i].reactivePower),
                str(tr[i].reactivePowerUncertainty),
                str(tr[i].voltage),
                str(tr[i].voltageUncertainty)
            ]))
        with open(filename, 'w') as file:
            file.write('\n'.join(lines))

        # Save the sent TransactiveRecord messages (i.e., sentSignal) as a copy
        # of the calculated set that was drawn upon by this method (i.e.,
        # mySignal).
        self.sentSignal = self.mySignal

    def schedule_power(self, mkt):
        # FUNCTION SCHEDULE_POWER() Calculate power for each time interval
        #
        # This is a basic method for calculating power generation of consumption in each active
        # time interval. It infers power generation or consumption from the supply or demand curves
        # that are represented by the neighbor's active vertices in the active time intervals.
        #
        # ASSUMPTIONS:
        # - all active vertices have been created and updated
        # - marginal prices have been updated and exist for all active intervals
        #
        # INPUTS:
        # agt - agent model object
        # mkt - Market object
        #
        # OUTPUTS:
        # updates array self.scheduledPowers

        #gather active time intervals ti
        time_intervals = mkt.timeIntervals # TimeInterval objects

        # index through active time intervals ti
        for i in range(len(time_intervals)):
            #extract marginal price value
            marginal_price = find_obj_by_ti(mkt.marginalPrices, time_intervals[i])
            marginal_price = marginal_price.value

            # find power corresponding to the marginal price according to the set of active
            # vertices in the indexed time interval. production() works for any power that
            # is determined by its supply curve or demand curve, as represented by the
            # active vertices
            value = production(self, marginal_price, time_intervals[i]) # [avg. kW]

            # check to see if a scheduled power already exists in this time interval
            interval_value = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            if interval_value is None:
                interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ScheduledPower, value)
                #append the scheduled power to the list of scheduled powers
                self.scheduledPowers.append(interval_value)
            else:
                interval_value.value = value # [avg. kW]

        
    #def update_production_costs(self, mkt):

    def update_vertices(self, auc):
        # UPDATE_VERTICES() - Update the active vertices that define the agent's residual
        # flexibility in the form of supply or demand curves
        #
        # The active vertices of non-transactive neighbors are relatively constant
        #
        # Active vertices must be created for new active time intervals.
        # Vertices may be affected by demand charges, too, as new demand-charge thresholds are
        # established.
        # Active vertices must also be checked and updated whenever a new transactive signal
        # is recieved.
        #
        # ASSUMPTIONS:
        # - time intervals are up-to-date
        # - at least one default vertex has been defined, should all other methods of 
        # establishing meaningful vertices fail
        # 
        # INPUTS: 
        # obj - agent model object
        # auc - acution object
        # 
        # OUTPUTS:
        # Updates self.activeVertices - an array of intervalValues that contain Vertex() structs

        # extract active time intervals
        time_intervals = auc.timeIntervals

        # delete any active vertices that are not in active time intervals, preventing time
        # intervals from accumulating indefinitely
        self.activeVertices = [x for x in self.activeVertices if x.timeInterval in time_intervals]

        # Index through actie time intervals
        for i in range(len(time_intervals)):
            # discard active vertices in the indexed time interval for creation later
            self.activeVertices = [x for x in self.activeVertices if x.timeInterval != time_intervals]

            # get default vertices
            default_vertices = self.defaultVertices

            if len(default_vertices) ==0:
                _log.warning( 'At least one default vertex must be defined for neighbor model object %s. '
                              'Scheduling was not performed' % (self.name) )
                return
            
            # check for transactive records in the indexed time interval
            received_vertices = [x for x in self.receivedSignal if x.timeInterval == time_intervals[i].name]

            if len(received_vertices) == 0:  #if isempty(received_vertices)
                #no records found, use defaults instead
                for k in range(len(default_vertices)):
                    value = default_vertices[k]
                    interval_value = IntervalValue(self, time_intervals[i], auc, MeasurementType.ActiveVertex, value)
                    # append the active vertex to the list of active vertices
                    self.activeVertices.append(interval_value)
            else:
                # sort received_vertices (which are transactiveRecord objects) by increasing price and power
                received_vertices = order_vertices(received_vertices)

                # prepare demand charge vertices
                demand_charge_flag = 0
                demand_charge_threshold = self.demandThreshold # [avg. kW]

                # calculate the peak in time intervals that come before the one now indexed by i
                # get all the scheduled powers
                prior_power = self.scheduledPowers # [avg. kW]

                if len(prior_power) < i+1: 
                    # especially the first iteration can encounter missing scheduled power 
                    # values. Place these out of the way by assigning them as small as possible.
                    # the current demand threshold will always overrule this value
                    prior_power = [float("-inf")]
                else:
                    #select only ones that occur prior to currently indexed value
                    prior_power = [x.value for x in prior_power[0:i+1]]

                predicted_power_peak = max(prior_power)
                demand_charge_threshold = max([demand_charge_threshold, predicted_prior_peak])

                # index through vertices in the recieved transactive records for the indexed time interval
                for k in range(len(received_vertices)):
                    # Record #0 is the balance point which must lie on existing segmetns of the supply
                    # demand curve. If there are multiple transactive records in the indexed time 
                    # interval, we don't need to create a vertex for Record #0.
                    if len(received_vertices) >= 3 and receivd_vertices[k].record==0:
                        continue
                    
                    # create working values of power and marginal price from the received vertices.
                    power = received_vertices[k].power
                    marginal_price = received_vertices[k].marginalPrice

                    # account for losses: if this agent imports power (positive) then there may be
                    # a loss term which would increase the marginal price
                    if power >0:
                        factor1 = (power/self.object.maximumPower)**2
                        factor2 = 1 + factor1*self.object.lossFactor
                        power = power/factor2
                        marginal_price = marginal_price *factor2

                        if power > demand_charge_threshold:
                            # power is greater than anticipated demand threshold. Demand charges are
                            # in play here, so set the flag
                            demand_charge_flag = k

                    #create corresponding (price, power) pair as an "active vertex"
                    value = Vertex(marginal_price, received_vertices[k].cost, power, received_vertices[k].powerUncertainty)

                    #create an active vertex interval value for the vertex in teh indexed time interval
                    interval_value = IntervalValue(self, time_intervals[i], auc, MeasurementType.ActiveVertex, value)

                    # append active vertex to list of active vertices
                    self.activeVertices.append(interval_value)

                # DEMAND CHARGES: 
                if demand_charge_flag !=0:
                    # there are demand charges
                    #get newly updated active vertices for the agent again
                    vertices = [x.value for x in self.activeVertices if x.timeInterval == time_intervals[i]]

                    #f find the marginal price corresponding to the demand-charge threshold
                    marginal_price = self.marginal_price_from_vertices(demand_charge_threshold, vertices)

                    # create first two vertices at the intersection of the demand-charge threshold and the
                    # supply or demand curve
                    vertex = Vertex(marginal_price, 0, demand_charge_threshold)

                    # create an intervalValue for the active vertex
                    interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertex)  # an IntervalValue object

                    #store the new active vertex interval value
                    self.activeVertices.append(interval_value)

                    # create the marginal price of the second of the two new vertices, augmented by the demand rate
                    marginal_price = marginal_price + self.demandRate

                    # create the second vertex
                    vertex = Vertex(marginal_price, 0, demand_charge_threshold)

                    # create the interval value for the second vertex
                    interval_value = IntervalValue(self, time_intervals[i], auc, MeasurementType.ActiveVertex, vertex)

                    # store active vertex
                    self.activeVertices.append(interval_value)

                    #check that vertices with power above the demand threshold have marginal prices
                    #that reflect the demand charge.
                    interval_values =[x for x in self.activeVertices if x.timeInterval == time_intervals[i]]

                    # index through current active vertices in the indexed time interval. These include 
                    # vertices from both prior to and after the introduction of demand-charge vertices
                    for k in range(len(interval_value)):
                        # extract the indexed vertex
                        vertex = interval_values[k].value
                        # extract the power of the indexed vertex
                        vertex_power = vertex.power
                        if vertex_power >demand_charge_threshold:
                            vertex.marginalPrice = vertex.marginalPrice + self.demandRate
                            interval_values[k].value = vertex

    
