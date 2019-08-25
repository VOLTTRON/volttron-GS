from datetime import datetime, timedelta
import numpy as np

import logging
#utils.setup_logging()
_log = logging.getLogger(__name__)

from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from market import Market
from interval_value import IntervalValue
from meter_point import MeterPoint
from auction_state import AuctionState
from time_interval import TimeInterval

class Auction(Market):
    #auction base class
    #An Auction object recieves bids for energy and price 
    #and reconciles the bids to reach a market clearing price
    #Every district heating or cooling loop must include an auction
    #to recieve signals from thermal assets and check that the mass
    #conservation law balances for the thermal loop

    def __init__(self, energy_type=MeasurementType.Heat):
        super(Auction, self).__init__()
        self.defaultPrice = 0.01 # [$/kWh]
        self.initialAuctionState = AuctionState.Inactive # enumeration
        self.measurementType = [energy_type]
        self.auctionOrder = 1 # ordering of sequential markets [pos. integer]
        #self.agentMembers = [] # agents which bid into the auction # list of strings
        if self.measurementType == MeasurementType.Heat:
            self.Treturn = 120 #set temperature of return steam in degrees C
            self.Tsupply = 250 #set temperature supply of steam in degrees C
            self.naturalGasPrice = 8.15 # [$/cubic foot]
            self.dieselGasPrice = 2.5 # [$/gallon]
        else:
            self.Treturn = 15 # set temperature return of cold water in degrees C
            self.Tsupply = 4 # set tmperature return of cold water in degrees C

    def retrieve_bids(self, agt):
        #FUNCTION RETRIEVE-BIDS() - Collect active vertices from Agent membes
        # and reassign them with aggregate system information for all active time intervals
        #
        # ASSUMPTIONS:
        # - Active time intervals exist and are up-to-date
        # - The active vertices of agent models exist and are up-to-date. The vertices
        # represent available power flexibility. The vertices include meaningful, accurate
        # production-cost information.
        # - There is agreement locally and in the network concerning the format, content,
        # and energy type (heat, cooling, electric) of transactive records.
        # - Calls method auction.sum_vertices in each time interval.
        #
        # INPUTS:
        # auc - auction object
        # agt - agents biding into auction
        #
        # OUTPUTS:
        # - updates auction.activeVertices - vertices that define the net system balance
        # and flexibility. The meaning of the vertex properties are 
        # - marginalPrice: marginal price [$/kWh]
        # - power: system net power at the vertex (the system "clears" where system net 
        #  power is zero)
        
        for ti in self.timeIntervals:
            # shift up the active vertices to the next timestep
            # The active vertices will be updated, but the ones from the last horizon auction
            # will be used as backup values in the event that convergence is not reached
            self.activeVertices = (self.activeVertices[1:]).append(self.activeVertices[0])
            
            # call the utility method auction.sum_vertices to update the aggregate vertices
            # in the inexed time interval.
            s_vertices = self.sum_vertices(agt, ti)

            # create and store interval values for each new aggregate vertex v
            i = 0
            for sv in s_vertices:
                iv = InternalValue(self, ti, self, MeasurementType.SystemVertex, sv) 
                self.activeVertices[i] = iv #update to interval values
                i = i+1

    # def balance(self, agt):
    #     # auc - auction object
    #     # agt - list of transactive agent objects

    #     # check and update the time intervals at the beginning of the process.
    #     # This should not be repeated in process iterations.
    #     self.check_intervals()

    #     # clean up or initialize marginal prices. 
    #     # this should not be repeated in process iterations
    #     self.check_marginal_prices()

    #     # Set a flag to indicate an unconverged condition.
    #     self.converged = False

    #     # Iterate to convergence. "Convergence" here refers to the status of the local
    #     # convergence of (1) local supply and demand and (2) dual costs.
    #     # This local convergence says nothing about the additional convergence
    #     # between transactive neighbors and their calculations.

    #     # Initialize the iteration counter k
    #     k = 1
    #     last_mp = [float('inf') for i in self.marginalPrices]

    #     while not self.converged and k<100:
    #         # Invite all agents to schedule themselves based on current marginal prices
    #         self.schedule(agt)

    #         # check for convergence: if there hasn't been a change in auction marginal price
    #         # then it is likely that all interrelated systems have converged
    #         if sum([np.abs(last_mp[i] - self.marginalPrices[i].value) for i in range(len(last_mp))]) <= 0.01:
    #             self.converged = True
            
    #         # if convergence hasn't been reached, update the marginal price
    #         self.update_costs(agt)
    #         last_mp = [price.value for price in self.marginalPrices]

    #         # Update the total supply and demand powers for each time interval
    #         self.update_supply_demand(agt)

    #         # display the iteration counter and the supply and demand gap
    #         # This may be commented out once we have confidence in the convergence
    #         # Check duality gap for convergence.
    #         # Calculate the duality gap, defined here as the relative difference
    #         # between total production and dual costs
    #         if self.totalProductionCost == 0:
    #             dg = float("inf")
    #         else:
    #             dg = self.totalProductionCost - self.totalDualCost  # [$]
    #             dg = dg / self.totalProductionCost  # [dimensionless. 0.01 is 1#]
            
            
    #         print("%i : %f\n" % (k, dg))
            

    #         # if auction is not converged, iterate. The next code in this method revised 
    #         # the marginal prices in active intervalse to drive the system toward balance and
    #         # convergence

    def check_intervals(self):
        # FUNCTION CHECK_INTERVALS()
        # Check or create the set of instatiated TimeIntervals in this Auction 

        # auc - auction object

        # Create the array "steps" of time intervals that should be active.
        # NOTE: Function Hours() corrects the behavior of Matlab function hours().
        steps = []
        cur_time = datetime.now()
        end_time = cur_time + self.futureHorizon
        step_time = self.marketClearingTime
        while step_time < end_time:
            if step_time > cur_time - self.marketClearingInterval:
                steps.append(step_time)
            step_time = step_time + self.marketClearingInterval

        # Index through the needed TimeIntervals based on their start times.
        for i in range(len(steps)):
            # This is a test to see whether the interval exists.
            # Case 0: a new interval must be created
            # Case 1: There is one match, the TimeInterval exists
            # Otherwise: duplicates exist and should be deleted

            tis = [x for x in self.timeIntervals if x.startTime == steps[i]]
            tis_len = len(tis)

            # no match was found, create a new TimeInterval
            if tis_len == 0:

                # create the TimeInterval
                # Modified 1/29 to use TimeInterval constructor
                at = steps[i] - self.futureHorizon
                dur = self.intervalDuration # duration
                mct = steps[i] # marketClearingTime
                st = steps[i] # startTime

                ti = TimeInterval(at, dur, self, mct, st)

                self.timeIntervals.append(ti)
            
            # The TimeInterval already exists
            elif tis_len == 1:
                #find the TimeInterval and check its auction state assignment
                tis[0].assign_state(self)

            # Duplicate time intervals exist. Remove all but one.
            else:
                self.timeIntervals = [tis[0]]
                #finish by checking and updating the TimeInterval's market state assignment
                tis[0].assign_state(self)

    # def check_marginal_prices(self):
    #     # FUNCTION CHECK_MARGINAL_PRICES()
    #     # Check that marginal prices exist for active time intervals. If they do
    #     # not exist for a time interval, choose from these alternatives that are
    #     # ordered from best to worst:
    #     # (1) initialize the marginal price from that of the preceding interval.
    #     # (2) use the default marginal price.
    #     # INPUTS:
    #     # auc: auction object
    #     # OUTPUTS:
    #     # populates list of active marginal prices (see class IntervalValue)

    #     # retrieve the list of active intervals ti
    #     ti = self.timeIntervals

    #     # clean up the list of active marginal prices. Remove any active marginal
    #     # prices that are not in active time intervals.
    #     self.marginalPrices = [x for x in self.marginalPrices if x.timeInterval in ti]

    #     # index through active time intervals ti
    #     for i in range (len(ti)):
    #         # check to see if a marginal price exists in the active time interval
    #         iv = find_obj_by_ti(self.marginalPrices, ti[i])

    #         if iv is None: # no marginal price found in indexed time interval
    #             # is a marginal price defined in the preceding time interval?

    #             # Extract the starting time st of the currently indexed time interval
    #             st = ti[i].startTime

    #             # calculate the starting time st of the previous time interval
    #             st = st - ti[i].duration

    #             # find the prior active time interval pti that has this calculated
    #             # starting time
    #             pti = find_obj_by_st(self.timeIntervals, st)

    #             # initialize previous marginal price value pmp as an empty set
    #             pmp = None
                
    #             if pti is not None:
    #                 # There is an active preceding time interval. Check wether there
    #                 # is an active marginal price in the previous time interval.
    #                 pmp = find_obj_by_ti(self.marginalPrices, pti)

    #             if pmp is None:
    #                 # no marginal price was found in the previous time interval
    #                 # assign the marginal price from a default value
    #                 value = self.defaultPrice # [$/kWh]

    #             else:
    #                 # a marginal price value was found in the previous time interval
    #                 # use that marginal price
    #                 value = pmp.value

    #             # create an interval value for the new marginal price in the indexed time
    #             # interval with either the default price or the marginal price from the
    #             # previous active time interval
    #             iv = IntervalValue(self, ti[i], self, MeasurementType.MarginalPrice, value)

    #             # append the marginal price value to the list of active marginal prices
    #             self.marginalPrices.append(iv) 


    # # def update_supply_demand(self, agt):
    # #     # FUNCTION UPDATE_SUPPY_DEMAND()
    # #     # For each time interval, sum the power that is generated, imported, 
    # #     # consumed, or exported for all bidding agents

    # #     # extract active time intervals
    # #     ti = self. timeIntervals

    # #     # index through the active time intervals ti
    # #     for i in range(len(ti)):
    # #         # initialize total generation tg
    # #         tg = 0.0

    # #         # initialize total demand td
    # #         td = 0.0

    # #         # index through agents
    # #         m = mtn.localAssets # cell array of local assets
    # #         for k in range(len(m)):
    # #             ao = find_obj_by_ti(agt[k].model.scheduledPowers, ti[i])

    # #             #extract and include the resource's scheduled power
    # #             p = mo.value

    # #             if p > 0: #generator
    # #                 tg = tg+p# [avg. kW]
    # #             else: #demand
    # #                 td = td+p #[avg. kW]

    # #         # updeate net power for the interval
    # #         # net power is the sum of total generation and total load
    # #         # by convention generation power is positive and consumption is negative

    # #         # check whether net power exists for the indexed time interval
    # #         iv = find_obj_by_ti(self.netPowers, ti[i])

    # #         if iv is None: # net power is not found in the indexed time interval
    # #             #create an interval value
    # #             iv = IntervalValue(self, ti[i], self, MeasurementType.NetPower, tg+td)

    # #             # append the net power to the list of net powers
    # #             self.netPowers.append(iv)

    # #         else:
    # #             # a net power was found in the indexed time interval.
    # #             # simply reassign its value.
    # #             iv.value = tg+td # [avg. kW]

    def view_marginal_prices(self):
        import matplotlib.pyplot as plt

        # gather active time series and make sure they are chronological order
        ti = self.timeIntervals
        ti = [x.startTime for x in ti] 
        ti.sort()

        if not isinstance(self, Auction):
            _log.warning('Object must be Auction')
            return
        else:
            mp = self.marginalPrices

        sorted_mp = sorted(mp, key=lambda x: (x.timeInterval.startTime))
        mp = [x.value for x in sorted_mp]

        fig = plt.figure() 
        ax = plt.axes() 

        ax.plot(ti, mp)
        plt.title('Marginal Prices in Active Time Intervals')
        plt.xlabel('time')
        plt.ylabel('marginal price ($/kWh}')


    # def view_net_curve(self, i):
    #     import matplotlib.pyplot as plt

    #     #gather active time series and make sure they are in chronological order
    #     ti = self.timeIntervals
    #     ti_objs = sort_vertices(ti, 'startTime')
    #     ti = [x.startTime for x in ti]
    #     ti.sort()

    #     if not isinstance(self, Market):
    #         _log.warning('Object must be a NeighborModel or LocalAssetModel')
    #         return
    #     else:
    #         mp = self.marginalPrice
        
    #     sorted_mp = sorted(mp, key=lambda x: x.timeInterval.startTime)
    #     mp = [x.value for x in sorted_mp]

    #     fig = plt.figure()
    #     ax = plt.axes()

    #     plt.title('Marginal Prices in Active Time Intervals')
    #     plt.xlabel('time')
    #     plt.ylabel('marginal price ($/kWh)')

    #     ti_objs = ti_objs[i]

    #     #find the active system vertices in the indexed time interval
    #     vertices = find_objs_by_ti(self.activeVertices, ti_objs)

    #     #extract the vertices 
    #     vertices = [x.value for x in vertices]

    #     # eliminate any vertices that have infinite marginal prices values
    #     vertices = [x for x in vertices if x.marginalPrice != float("inf")]

    #     # sort the active vertices in the indexed time interval by power and by marginal price
    #     vertices = order_vertices(vertices)

    #     #calculate the extremes and range of the horizontal marginal-price axis
    #     x = [x.marginalPrice for x in vertices]
    #     minx = min(x)
    #     maxx = max(x)
    #     xrange = maxx-minx

    #     #calculate the extremes and range of the vertical power axis
    #     y = [x.power for x in vertices]
    #     miny = min(y)
    #     maxy = max(y)
    #     yrange = maxy - miny

    #     # perform scaling if power range is large
    #     if yrange > 1000:
    #         unit = '(MW)'
    #         factor = 0.001
    #         miny = factor * miny
    #         maxy = factor * maxy
    #         yrange = factor * yrange
    #     else:
    #         unit = '(kW)'
    #         factor = 1.0

    #     # create a horizontal line at zero
    #     plt.plot([minx-0.1*xrange, maxx+0.1*xrange], [0.0, 0.0])

    #     # draw a line from the left figure boundary to the first vertex
    #     plt.plot([minx -0.1*xrange, vertices[0].marginalPrice], [factor*vertices[0].power, factor*vertices[0].power])

    #     #draw lines from each vertex to the next. If two successive vertices are not continuous
    #     # no liine should be drawn
    #     for i in range(len(vertices)-1):
    #         linestyle = ''
    #         if vertices[i].continuity == 0 and vertices[i+1].continuity ==0:
    #             linestyle = ''
    #         else:
    #             linestyle = '-'

    #         plt.plot([vertices[i].marginalPrice, vertices[i+1].marginalPrice], 
    #                 [factor*vertices[i].power, factor*vertices[i+1].power],
    #                 linestyle = linestyle)

    #         plt.title('Production Vertices (' + ti_objs.name + ')')
    #         plt.xlabel('unit price ($/kWh)')
    #         plt.ylabel('power' + str(unit))
    #         plt.show()


