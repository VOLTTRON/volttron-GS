from datetime import datetime, timedelta

import logging
#utils.setup_logging()
_log = logging.getLogger(__name__)

from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from interval_value import IntervalValue
from meter_point import MeterPoint
from market_state import MarketState
from time_interval import TimeInterval


class Market:
    # Market Base Class
    # A Market object may be a formal driver of myTransactiveNode's
    # responsibilities within a formal market. At least one Market must exist
    # (see the firstMarket object) to drive the timing with which new
    # TimeIntervals are created.
    
    def __init__(self, measurementType = [MeasurementType.PowerReal]):
        self.activeVertices = [[] for mt in measurementType]  # IntervalValue.empty  # values are vertices
        self.blendedPrices1 = []  # IntervalValue.empty  # future
        self.blendedPrices2 = []  # IntervalValue.empty  # future
        self.commitment = False
        self.converged = False
        self.defaultPrice = [0.05 for mt in measurementType]  # [$/kWh]
        self.dualCosts = [[] for mt in measurementType]   # IntervalValue.empty  # values are [$]
        self.dualityGapThreshold = 0.01  # [dimensionless, 0.01 = 1#]
        self.futureHorizon = timedelta(hours=24)  # [h]                                          # [h]
        self.initialMarketState = MarketState.Inactive  # enumeration
        self.intervalDuration = timedelta(hours=1)  # [h]
        self.intervalsToClear = 1  # postitive integer
        self.marginalPrices = [[] for mt in measurementType]   # IntervalValue.empty  # values are [$/kWh]
        self.marketClearingInterval = timedelta(hours=1)  # [h]
        self.marketClearingTime = []  # datetime.empty  # when market clears
        self.measurementType = measurementType # types of energy that must be balanced on this market
        self.method = 2  # Calculation method {1: subgradient, 2: interpolation}
        self.marketOrder = 1  # ordering of sequential markets [pos. integer]
        self.name = ''
        self.netPowers = [[] for mt in measurementType]   # IntervalValue.empty  # values are [avg.kW]
        self.nextMarketClearingTime = []  # datetime.empty  # start of pattern
        self.productionCosts = [[] for mt in measurementType]  # IntervalValue.empty  # values are [$]
        self.timeIntervals = []  # TimeInterval.empty  # struct TimeInterval
        self.totalDemand = [[] for mt in measurementType]  # IntervalValue.empty  # [avg.kW]
        self.totalDualCost = [0.0 for mt in measurementType]*len(measurementType)  # [$]
        self.totalGeneration = [[] for mt in measurementType]   # IntervalValue.empty  # [avg.kW]
        self.totalProductionCost = [[] for mt in measurementType]   # [$]

    def assign_system_vertices(self, mtn):
        # FUNCTION ASSIGN_SYSTEM_VERTICES() - Collect active vertices from neighbor
        # and asset models and reassign them with aggregate system information for
        # all active time intervals.
        #
        # ASSUMPTIONS:
        # - Active time intervals exist and are up-to-date
        # - Local convergence has occurred, meaning that power balance, marginal
        # price, and production costs have been adequately resolved from the
        # local agent's perspective
        # - The active vertices of local asset models exist and are up-to-date.
        # The vertices represent available power flexibility. The vertices
        # include meaningful, accurate production-cost information.
        # - There is agreement locally and in the network concerning the format
        # and content of transactive records
        # - Calls method mkt.sum_vertices in each time interval.
        #
        # INPUTS:
        # mkt - Market object
        # mtn - myTransactiveNode object
        #
        # OUTPUTS:
        # - Updates mkt.activeVertices - vertices that define the net system
        # balance and flexibility. The meaning of the vertex properties are
        # - marginalPrice: marginal price [$/kWh]
        # - cost: total production cost at the vertex [$]. (A locally
        #   meaningful blended electricity price is (total production cost /
        #   total production)).
        # - power: system net power at the vertex (The system "clears" where
        #   system net power is zero.)
        if hasattr(self, 'measurementType'):
            n_power_types = len(self.measurementType)
        else:
            n_power_types = 1

        for ti in self.timeIntervals:
            # iterate through energy types
            for i_energy_type in range(n_power_types):
                if hasattr(self, 'measurementType'):
                    this_energy_type = self.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal                

                # Find and delete existing aggregate active vertices in the indexed
                # time interval. These shall be recreated.
                #ind = ~ismember([mkt.activeVertices.timeInterval], ti[i])  # logical array
                #mkt.activeVertices = mkt.activeVertices(ind)  # IntervalValues
                self.activeVertices[i_energy_type] = [x for x in self.activeVertices[i_energy_type] if x != ti]

                # Call the utility method mkt.sum_vertices to recreate the
                # aggregate vertices in the indexed time interval. (This method is
                # separated out because it will be used by other methods.)
                s_vertices = self.sum_vertices(mtn, ti, energy_type = this_energy_type)

                # Create and store interval values for each new aggregate vertex v
                # if you have multiple energy types, then save them separately
                for sv in s_vertices:
                    iv = IntervalValue(self, ti, self, MeasurementType.SystemVertex, sv) # an IntervalValue
                    self.activeVertices[i_energy_type].append(iv)

    def balance(self, mtn):
        # mkt - Market object
        # mtn - my transactive node object

        # Check and update the time intervals at the begining of the process.
        # This should not need to be repeated in process iterations.
        self.check_intervals()

        # Clean up or initialize marginal prices. This should not be
        # repeated in process iterations.
        self.check_marginal_prices()

        # Set a flag to indicate an unconverged condition.
        self.converged = False

        # Iterate to convergence. "Convergence" here refers to the status of the
        # local convergence of (1) local supply and demand and (2) dual costs.
        # This local convergence says nothing about the additional convergence
        # between transactive neighbors and their calculations.

        # Initialize the iteration counter k
        k = 1

        while not self.converged and k < 100:

            # Invite all neighbors and local assets to schedule themselves
            # based on current marginal prices
            self.schedule(mtn)

            # Update the primal and dual costs for each time interval and
            # altogether for the entire time horizon.
            self.update_costs(mtn)

            # Update the total supply and demand powers for each time interval.
            # These sums are needed for the sub-gradient search and for the
            # calculation of blended price.
            self.update_supply_demand(mtn)

            # Check duality gap for convergence.
            # Calculate the duality gap, defined here as the relative difference
            # between total production and dual costs
            if self.totalProductionCost == 0:
                dg = float("inf")
            else:
                dg = self.totalProductionCost - self.totalDualCost  # [$]
                dg = dg / self.totalProductionCost  # [dimensionless. 0.01 is 1#]

            # Display the iteration counter and duality gap. This may be
            # commented out once we have confidence in the convergence of the
            # iterations.
            print("%i : %f\n" % (k, dg))

            # Check convergence condition
            if abs(dg) <= self.dualityGapThreshold:  # Converged

                # 1.3.1 System has converged to an acceptable balance.
                self.converged = True
            
            # System is not converged. Iterate. The next code in this
            # method revised the marginal prices in active intervals to drive
            # the system toward balance and convergence.

            # Gather active time intervals ti
            ti = self.timeIntervals  # TimeIntervals

            # A parameter is used to determine how the computational agent
            # searches for marginal prices.
            #
            # Method 1: Subgradient Search - This is the most general solution
            # technique to be used on non-differentiable solution spaces. It uses the
            # difference between primal costs (mostly production costs, in this case)
            # and dual costs (which are modified using gross profit or consumer cost)
            # to estimate the magnitude of power imbalance in each active time
            # interval. Under certain conditions, a solution is guaranteed. Many
            # iterations may be needed. The method can be fooled, so I've found, by
            # interim oscilatory solutions. This method may fail when large
            # assets have linear, not quadratic, cost functions.
            #
            # Methods 2: Interpolation - If certain requirements are met, the solution
            # might be greatly accelerated by interpolatig between the inflection
            # points of the net power curve.
            # Requirement 1: All Neighbors and LocalAssets are represented by linear
            # or quadratic cost functions, thus ensuring that the net power curve
            # is perfectly linear between its inflecion points.
            # Requirement 2: All Neighbors and Assets update their active vertices in
            # a way that represents their residual flexibility, which can be none,
            # thus ensuring a meaningful connection between balancing in time
            # intervals and scheduling of the individual Neighbors and LocalAssets.
            # This method might fail when many assets do complex scheduling of
            # their flexibilty.

            if self.method == 2:
                self.assign_system_vertices(mtn)

            # check for multiple energy types
            if hasattr(self, 'measurementType'):
                n_energy_types = len(self.measurementType)
            else:
                n_energy_types = 1

            # Index through active time intervals.
            for i in range(len(ti)):
                # index though energy types
                for i_energy_type in range(n_energy_types):

                    # Find the marginal price interval value for the
                    # corresponding indexed time interval.
                    #mp = findobj(mkt.marginalPrices, 'timeInterval', ti[i])  # an IntervalValue
                    mp = find_obj_by_ti(self.marginalPrices[i_energy_type], ti[i])

                    # Extract its  marginal price value.
                    xlamda = mp.value  # [$/kWh]
                    
                    if self.method == 1:

                        # Find the net power corresponding to the indexed time
                        # interval.
                        #np = findobj(mkt.netPowers, 'timeInterval', ti[i])  # an IntervalValue
                        #tg = findobj(mkt.totalGeneration, 'timeInterval', ti[i])
                        #td = findobj(mkt.totalDemand, 'timeInterval', ti[i])
                        np = find_obj_by_ti(self.netPowers[i_energy_type], ti[i])
                        tg = find_obj_by_ti(self.totalGeneration[i_energy_type], ti[i])
                        td = find_obj_by_ti(self.totalDemand[i_energy_type], ti[i])
                        
                        np = np.value / (tg.value - td.value)

                        # Update the marginal price using subgradient search.
                        xlamda = xlamda - (np * 1e-1) / (10 + k)  # [$/kWh]

                    elif self.method == 2:

                        # Get the indexed active system vertices
                        #av = findobj(mkt.activeVertices, 'timeInterval', ti[i])
                        #av = [av.value]
                        av = [x.value for x in self.activeVertices[i_energy_type] if x.timeInterval == ti[i]]

                        # Order the system vertices in the indexed time interval
                        av = order_vertices(av)

                        # Find the vertex that bookcases the balance point from the
                        # lower side.
                        #lower_av = av([av.power] <= 0)
                        #lower_av = lower_av(len(lower_av))
                        #lower_av = max([x for x in av if x.power <= 0])
                        av2 = [x for x in av if x.power<=0 and x.marginalPrice != float('inf')]
                        lower_av = sort_vertices(av2, 'marginalPrice')

                        # Find the vertex that bookcases the balance point from the
                        # upper side.
                        #upper_av = av([av.power] >= 0)
                        #upper_av = upper_av(1)
                        #upper_av = min([x for x in av if x.power >= 0])
                        av2 = [x for x in av if x.power>0]
                        upper_av = sort_vertices(av2, 'marginalPrice')
                        
                        power_range = 0
                        if len(lower_av)>0 and len(upper_av)>0:
                            lower_av = lower_av[-1]
                            upper_av = upper_av[0]
                            power_range = upper_av.power-lower_av.power

                        if power_range!=0:
                            # Interpolate the marginal price in the interval using a
                            # principle of similar triangles.
                            mp_range = upper_av.marginalPrice - lower_av.marginalPrice
                            xlamda = - mp_range * lower_av.power / power_range + lower_av.marginalPrice
                        else:
                            power_range = 0
                            mp_range = 0
                            xlamda = sort_vertices(av, 'marginalPrice')[0].marginalPrice

                    # Regardless of the method used, variable "xlamda" should now hold
                    # the updated marginal price. Assign it to the marginal price
                    # value for the indexed active time interval.
                    mp.value = xlamda  # [$/kWh]

            # Increment the iteration counter.
            k = k + 1

        if not self.converged:
            # Not converged. Need to do something..
            pass

    def calculate_blended_prices(self):
        # FUNCTION CALCULATE_BLENDED_PRICES()
        # Calculate the blended prices for active time intervals.
        #
        # The blended price is the averaged weighted price of all locally
        # generated and imported energies. A sum is made of all costs of
        # generated and imported energies, which are prices weighted by their
        # corresponding energy. This sum is divided by the total generated and
        # imported energy to get the average.
        #
        # The blended price does not include supply surplus and may therefore be
        # a preferred representation of price for local loads and friendly
        # neighbors, for which myTransactiveNode is not competitive and
        # profit-seeking.
        #
        # mkt - Market object
        
        # Update and gather active time intervals ti. It's simpler to
        # recalculate the active time intervals than it is to check for
        # errors.
        
        self.check_intervals()
        ti = self.timeIntervals
        
        # Gather primal production costs of the time intervals.
        
        pc = self.productionCosts
        
        # Perform checks on interval primal production costs to ensure smooth
        # calculations. NOTE: This does not check the veracity of the
        # primal costs.
        
        # CASE 1: No primal production costs have been populated for the various
        # assets and neighbors. This results in termination of the
        # process.
        
        if pc is None or len(pc) == 0:  # isempty(pc)
            _log.warning('Primal costs have not yet been calculated.')
            return
        
        # CASE 2: There is at least one active time interval for which primal
        # costs have not been populated. This results in termination of the
        # process.
        
        elif len(ti) > len(pc):
            _log.warning('Missing primal costs for active time intervals.')
            return
        
        # CASE 3: There is at least one extra primal production cost that does
        # not refer to an active time interval. It will be removed.
        
        elif len(ti) < len(pc):
            _log.warning('Removing primal costs that are not among active time intervals.')
            #im_ti = [x.timeInterval for x in mkt.productionCosts]
            #im = ismember(im_ti, mkt.timeIntervals)
            #mkt.productionCosts = mkt.productionCosts(im)
            self.productionCosts = [x for x in self.productionCosts if x.timeInterval in self.timeIntervals]
        
        for i in range(len(ti)):  # for i = 1:len(ti)
            #pc = findobj(mkt.productionCosts, 'timeInterval', ti[i])
            #tg = find.obj(mkt.totalGeneration, 'timeInterval', ti[i])
            pc = find_obj_by_ti(self.productionCosts, ti[i])
            tg = find_obj_by_ti(self.totalGeneration, ti[i])
            bp = pc / tg
            
            #nti = ~ismember(mkt.blendedPrices1, 'timeInterval', ti[i])
            #mkt.blendedPrices1 = mkt.blendedPrices1(nti)
            self.blendedPrices1 = [x for x in self.blendedPrices1 if x != ti[i]]
            
            val = bp
            iv = IntervalValue(self, ti[i], self, MeasurementType.BlendedPrice, val)
            
            # Append the blended price to the list of interval values
            self.blendedPrices1.append(iv)  # mkt.blendedPrices1 = [mkt.blendedPrices1, iv]
        
    def check_intervals(self):
        # FUNCTION CHECK_INTERVALS()
        # Check or create the set of instantiated TimeIntervals in this Market
        #
        # mkt - Market object
        
        # Create the array "steps" of time intervals that should be active.
        # NOTE: Function Hours() corrects the behavior of Matlab function
        # hours().
        #steps = datetime(mkt.marketClearingTime): Hours(mkt.marketClearingInterval): datetime + Hours(mkt.futureHorizon)
        #steps = steps(steps > datetime - Hours(mkt.marketClearingInterval))
        steps = []
        cur_time = datetime.now()
        end_time = cur_time + self.futureHorizon
        step_time = self.marketClearingTime
        while step_time < end_time:
            if step_time > cur_time - self.marketClearingInterval:
                steps.append(step_time)
            step_time = step_time + self.marketClearingInterval
            
        # Index through the needed TimeIntervals based on their start times.
        for i in range(len(steps)):  #for i = 1:len(steps)
            # This is a test to see whether the interval exists.
            # Case 0: a new interval must be created
            # Case 1: There is one match, the TimeInterval exists
            # Otherwise: Duplicates exists and should be deleted.

            #switch len(findobj(mkt.timeIntervals, 'startTime', steps(i)))
            tis = [x for x in self.timeIntervals if x.startTime == steps[i]]
            tis_len = len(tis)
            
            # No match was found. Create a new TimeInterval.
            if tis_len == 0:
                
                # Create the TimeInterval
                # Modified 1/29 to use TimeInterval constructor
                at = steps[i] - self.futureHorizon  # activationTime
                dur = self.intervalDuration  # duration
                mct = steps[i]  # marketClearingTime
                st = steps[i]  # startTime
                
                ti = TimeInterval(at, dur, self, mct, st)
                
                # ELIMINATE HURKY INLINE CONSTRUCTION BELOW
                # ti = TimeInterval()
                #
                #     #Populate the TimeInterval properties
                #
                #     ti.name = char(steps[i],'yyMMdd-hhmm')
                #     ti.startTime = steps[i]
                #     ti.active = True
                #     ti.duration = Hours(mkt.intervalDuration)
                #     ti.marketClearingTime = steps[i]
                #     ti.market = mkt
                #     ti.activationTime = steps[i]-Hours(mkt.futureHorizon)
                #     ti.timeStamp = datetime
                #
                #     #assign marketState property
                #
                #     ti.assign_state(ti.market)
                # ELIMINATE HURKY INLINE CONSTRUCTOR ABOVE
                
                # Store the new TimeInterval in Market.timeIntervals
                
                self.timeIntervals.append(ti)  # = [mkt.timeIntervals, ti]
                
            # The TimeInterval already exists.
            elif tis_len == 1:
                
                # Find the TimeInterval and check its market state assignment.
                #ti = findobj(mkt.timeIntervals, 'startTime', steps(i))
                tis[0].assign_state(self)  # ti.assign_state(mkt)
                
            # Duplicate time intervals exist. Remove all but one.
            else:
                
                # Get rid of duplicate TimeIntervals.
                #mkt.timeIntervals = unique(mkt.timeIntervals)
                #tmp = []
                #for x in mkt.timeIntervals:
                #  if x not in tmp:
                #      tmp.append(x)
                #mkt.timeIntervals = tmp

                # Find the remaining TimeInterval having the startTime step(i).
                #ti = findobj(mkt.timeIntervals, 'startTime', steps(i))
                #tis = [x for x in mkt.timeIntervals if x.startTime == steps[i]]
                self.timeIntervals = [tis[0]]

                # Finish by checking and updating the TimeInterval's
                # market state assignment.
                tis[0].assign_state(self)

    def check_marginal_prices(self):
        # FUNCTION CHECK_MARGINAL_PRICES()
        # Check that marginal prices exist for active time intervals. If they do
        # not exist for a time interval, choose from these alternatives that are
        # ordered from best to worst:
        # (1) initialize the marginal price from that of the preceding
        # interval.
        # (2) use the default marginal price.
        # INPUTS:
        # mkt     market object
        # OUTPUTS:
        # populates list of active marginal prices (see class IntervalValue)
        #
        # [Checked on 12/21/17]
        
        # Check and retrieve the list of active intervals ti
        
        #  mkt.check_intervals #This should have already been done.
        ti = self.timeIntervals
        
        # Clean up the list of active marginal prices. Remove any active
        # marginal prices that are not in active time intervals.
        #ind = ismember([mkt.marginalPrices.timeInterval], ti)
        #mkt.marginalPrices = mkt.marginalPrices(ind)
        if hasattr(self, 'measurementType'):
            n_energy_types = len(self.measurementType)
            for i_energy_type in range(n_energy_types):
                self.marginalPrices[i_energy_type] = [x for x in self.marginalPrices[i_energy_type] if x.timeInterval in ti]
        else:
            self.marginalPrices = [x for x in self.marginalPrices if x.timeInterval in ti]
        
        # Index through active time intervals ti
        for i in range(len(ti)):  #for i = 1:len(ti)
            # Index through energy types
            if hasattr(self, 'measurementType'):
                for i_energy_type in range(n_energy_types):
                    
                    # Check to see if a marginal price exists in the active time
                    # interval
                    #iv = findobj(mkt.marginalPrices, 'timeInterval', ti[i])
                    iv = find_obj_by_ti(self.marginalPrices[i_energy_type], ti[i])

                    if iv is None:  # if isempty(iv)

                        # No marginal price was found in the indexed time interval. Is
                        # a marginal price defined in the preceding time interval?

                        # Extract the starting time st of the currently indexed time interval
                        st = ti[i].startTime

                        # Calculate the starting time st of the previous time interval
                        st = st - ti[i].duration

                        # Find the prior active time interval pti that has this
                        # calculated starting time

                        #pti = findobj(mkt.timeIntervals, 'startTime', st)
                        pti = find_obj_by_st(self.timeIntervals, st)  # prior time interval

                        # Initialize previous marginal price value pmp as an empty set
                        pmp = None  # prior marginal prices

                        if pti is not None:  #if ~isempty(pti)

                            # There is an active preceding time interval. Check whether
                            # there is an active marginal price in the previous time interval.
                            #pmp = findobj(mkt.marginalPrices, 'timeInterval', pti)  # an IntervalValue
                            pmp = find_obj_by_ti(self.marginalPrices[i_energy_type], pti)

                        if pmp is None:

                            # No marginal price was found in the previous time interval
                            # either. Assign the marginal price from a default value.
                            value = self.defaultPrice[i_energy_type]  # [$/kWh]

                        else:

                            # A marginal price value was found in the previous time
                            # interval. Use that marginal price.
                            value = pmp.value  # [$/kWh]

                        # Create an interval value for the new marginal price in the
                        # indexed time interval with either the default price or the
                        # marginal price from the previous active time interval.
                        iv = IntervalValue(self, ti[i], self, MeasurementType.MarginalPrice, value)

                        # Append the marginal price value to the list of active marginal prices
                        self.marginalPrices[i_energy_type].append(iv)

            # if it's not divided by energy type, then there is only one energy type
            else:
                    # Check to see if a marginal price exists in the active time
                # interval
                #iv = findobj(mkt.marginalPrices, 'timeInterval', ti[i])
                iv = find_obj_by_ti(self.marginalPrices, ti[i])

                if iv is None:  # if isempty(iv)

                    # No marginal price was found in the indexed time interval. Is
                    # a marginal price defined in the preceding time interval?

                    # Extract the starting time st of the currently indexed time interval
                    st = ti[i].startTime

                    # Calculate the starting time st of the previous time interval
                    st = st - ti[i].duration

                    # Find the prior active time interval pti that has this
                    # calculated starting time

                    #pti = findobj(mkt.timeIntervals, 'startTime', st)
                    pti = find_obj_by_st(self.timeIntervals, st)  # prior time interval

                    # Initialize previous marginal price value pmp as an empty set
                    pmp = None  # prior marginal prices

                    if pti is not None:  #if ~isempty(pti)

                        # There is an active preceding time interval. Check whether
                        # there is an active marginal price in the previous time interval.
                        #pmp = findobj(mkt.marginalPrices, 'timeInterval', pti)  # an IntervalValue
                        pmp = find_obj_by_ti(self.marginalPrices, pti)

                    if pmp is None:

                        # No marginal price was found in the previous time interval
                        # either. Assign the marginal price from a default value.
                        value = self.defaultPrice # [$/kWh]

                    else:

                        # A marginal price value was found in the previous time
                        # interval. Use that marginal price.
                        value = pmp.value  # [$/kWh]

                    # Create an interval value for the new marginal price in the
                    # indexed time interval with either the default price or the
                    # marginal price from the previous active time interval.
                    iv = IntervalValue(self, ti[i], self, MeasurementType.MarginalPrice, value)

                    # Append the marginal price value to the list of active marginal prices
                    self.marginalPrices.append(iv)
                

    def schedule(self, mtn):
        # Process called to
        # (1) invoke all models to update the scheduling of their resources, loads, or neighbor
        # (2) converge to system balance using sub-gradient search.
        #
        # mkt - Market object
        # mtn - my transactive node object
        
        # 1.2.1 Call resource models to update their schedules
        # Call each local asset model m to schedule itself.
        for la in mtn.localAssets:
            la.model.schedule(self)
        
        # 1.2.2 Call neighbor models to update their schedules
        # Call each neighbor model m to schedule itself
        for n in mtn.neighbors:
            n.model.schedule(self)

    def sum_vertices(self, mtn, ti, energy_type=MeasurementType.PowerReal, *args, **kwargs):
        # FUNCTION SUM_VERTICES() - Create system vertices with system information
        # for a single time interval. An optional argument allows the exclusion of
        # a transactive neighbor object, which is useful for transactive records
        # and their corresponding demand or supply curves.
        # This utility method should be used for creating transactive signals (by
        # excluding the neighbor object), and for visualization tools that review
        # the local system's net supply/demand curve. A labeled input for the energy
        # type to be summed is included
        #
        # VERSIONING
        # 0.1 2018-01 Hammerstrom
        # - Original method draft completed
        # 0.2 2019-05 Panossian
        # - modified to allow specification of an energy type to be summed
        
        # Check if a fourth argument, an object to be excluded, was used
        # Initialize "object to exclude" ote
        nvarargin = len(args)
        ote = None
        
        if nvarargin > 0:
        
            # A fourth argument was used. Assign it as an object to exclude ote.
            # NOTE: Curly braces must be used with varargin{} to properly
            # reference contects.
            ote = args[0]  # a neighbor or asset model object
        
        # Initialize a list of marginal prices mps at which vertices will be
        # created.
        # It is computationally wise to pre-allocate vector memory. This is
        # accomplished here by padding with 100 zeros and using a counter.
        #mps = [0]*100  #zeros(1, 100)  # marginal prices [$/kWh]
        #mps_cnt = 0
        mps = []

        # Gather the list of active neighbor objects n
        n = mtn.neighbors  # cell array of neighbors
        
        # Index through the active neighbor objects n
        for i in range(len(n)):  #for i = 1:len(n)
            # Change the reference to the corresponding neighbor model
            nm = n[i].model  #nm = n{i}.model  # a neighbor model
        
            # check to see if this neighbor has the right energy type
            if hasattr(nm, 'measurementType'):
                if energy_type in nm.measurementType:
                    i_energy_type = nm.measurementType.index(energy_type)

                    # jump out of this iteration if neighbor model happens to be the 
                    # "object to exclude" ote
                    if ote is not None:
                        if nm == ote:
                            continue

                    # find the neighbor model's active vertice in this time interval for this energy type
                    mp = find_objs_by_ti(nm.activeVertices[i_energy_type], ti)

                # if this neighbor doesn't have the right energy type, jump out of this iteration
                else:
                    continue

            # if this neighbor doesn't specify energy types, assume it is the correct one
            else:                
                # Jump out of this iteration if neighbor model nm happens to be the
                # "object to exclude" ote
                if ote is not None:  #if ~isempty(ote)
                    if nm == ote:
                        continue
                
                # Find the neighbor model's active vertices in this time interval
                #mp = findobj(nm.activeVertices, 'timeInterval', ti)  # IntervalValues
                mp = find_objs_by_ti(nm.activeVertices, ti)
            
            if len(mp) > 0:  #if ~isempty(mp)
            
                # At least one active vertex was found in the time interval
                # Extract the vertices from the interval values
                mp = [x.value for x in mp]  # Vertices
            
                if len(mp) == 1:
                    # There is one vertex. This means the power is constant for
                    # this neighbor. Enforce the policy of assigning infinite
                    # marginal price to constant vertices.
                    mp = [float("inf")]  # marginal price [$/kWh]
            
                else:
            
                    # There are multiple vertices. Use the marginal price values
                    # from the vertices themselves.
                    mp = [x.marginalPrice for x in mp]  # marginal prices [$/kWh]

            
                # Increment the index counter
                #mps_cnt_start = mps_cnt + 1
                #mps_cnt = mps_cnt + len(mp)  # index counter
            
                # Warn if vector counter exceeds its original allocation
                #if mps_cnt > 100:
                #    _log.warning('vector length has exceeded its preallocation')
            
                # Append the marginal price to the list of marginal prices mps
                #mps(mps_cnt_start:mps_cnt) = mp  # marginal prices [$/kWh]
                mps.extend(mp)
            
        # Gather the list of active local asset objects n
        n = mtn.localAssets  # a cell array of localAssets
        
        for i in range(len(n)):  #for i = 1:len(n)
            # Change the reference to the corresponding local asset model
            nm = n[i].model  # a local asset model
            
            # Jump out of this iteration if local asset model nm happens to be
            # the "object to exclude" ote
            if ote is not None:
                if nm == ote:
                    continue

            # if this model has a list of energy types, check to see if it has this energy type
            if hasattr(nm, 'measurementType'):
                if energy_type in nm.measurementType:
                    i_energy_type = nm.measurementType.index(energy_type)
                else:
                    continue

                # if it has the correct energy type then 
                mp = find_objs_by_ti(nm.activeVertices[i_energy_type], ti)

            # if the model doesn't specify an energy type, assume it's electric
            elif energy_type== MeasurementType.PowerReal:
                # Find the local asset model's active vertices in this time interval
                #mp = findobj(nm.activeVertices, 'timeInterval', ti)  # IntervalValues
                mp = find_objs_by_ti(nm.activeVertices, ti)

            if len(mp) > 0:  # if ~isempty(mp)
            
                # At least one active vertex was found in the time interval
                # Extract the vertices from the interval values
                mp = [x.value for x in mp]  # mp = [mp.value]  # Vertices

                # Extract the marginal prices from the vertices
            
                if len(mp) == 1:
            
                    # There is one vertex. This means the power is constant for
                    # this local asset. Enforce the policy of assigning infinite
                    # marginal price to constant vertices.
            
                    mp = [float("inf")]  # marginal price [$/kWh]
            
                else:
            
                    # There are multiple vertices. Use the marginal price values
                    # from the vertices themselves.

                    mp = [x.marginalPrice for x in mp]  # marginal prices [$/kWh]

            
                # Increment the index counter
                #mps_cnt_start = mps_cnt + 1
                #mps_cnt = mps_cnt + len(mp)  # index counter
            
                # Warn if vector counter exceeds its original allocation
                #if mps_cnt > 100
                #    _log.warning('vector length has exceeded its preallocation')

            
                # Append the marginal price to the list of marginal prices mps
                #mps(mps_cnt_start:mps_cnt) = mp  # marginal prices [$/kWh]
                mps.extend(mp)
        
        # Trim mps, which was originally padded with zeros.
        #mps = mps(1:mps_cnt)  # marginal prices [$/kWh]
        
        ## A list of vertex marginal prices have been created.
        
        # Sort the marginal prices from least to greatest
        mps.sort()  # marginal prices [$/kWh]
        
        # Ensure that no more than two vertices will be created at the same
        # marginal price. The third output of function unique() is useful here
        # because it is the index of unique entries in the original vector.
        #[~, ~, ind] = unique(mps)  # index of unique vector contents
        
        # Create a new vector of marginal prices. The first two entries are
        # accepted because they cannot violate the two-duplicates rule. The
        # vector is padded with zeros, which should be compuationally efficient.
        # A counter is used and should be incremented with new vector entries.
        #if mps_cnt < 3
        #    mps_new = mps
        #else:
        #    mps_new = [mps(1:2), zeros(1, 98)]  # marginal prices [$/kWh]
        #    mps_cnt = 2  # indexing counter
        mps_new = None
        if len(mps)>=3:
            mps_new = [mps[0], mps[1]]
        else:
            mps_new = list(mps)


        # Index through the indices and append the new list only when there are
        # fewer than three duplicates.
        #for i = 3:len(ind)
        
            # A violation of the two-duplicate rule occurs if an entry is the
            # third duplicate. If this case, jump out of the loop to the next
            # iteration.
        #    if ind(i) == ind(i - 1) and ind(i - 1) == ind(i - 2):
            
        #        continue
            
        #    else:
            
                # There are no more than two duplicates.
            
                # Increment the vector indexing counter
        #        mps_cnt = mps_cnt + 1
            
                # Warn if the vector's preallocation size is becoming exceeded
        #        if mps_cnt > 100
        #            _log.warning('vector length has exceeded its preallocation')

            
                # Append the list of marginal prices with the indexed marginal
                # price.
        #        mps_new(mps_cnt) = mps(i)  # marginal prices [$/kWh]
            
        for i in range(2, len(mps)):
            if mps[i] != mps[i-1] or mps[i-1] != mps[i-2]:
                mps_new.append(mps[i])


        # Trim the new list of marginal prices mps_new that had been padded with
        # zeros and rename it mps
        #mps = mps_new(1:mps_cnt)  # marginal prices [$/kWh]
        mps = mps_new


        if len(mps) >= 2:  # if mps_cnt >= 2
        
            # There are at least two marginal prices. (This is a condition that
            # is unlikely but was found in testing of version 1.1.)
            #if mps(mps_cnt) == float("inf") and mps(mps_cnt - 1) == float("inf"):
            if mps[-1] == float('inf') and mps[-2] == float('inf'):
        
                # A duplicate infinite marginal price, which is used to indicate a
                # constant, inelastic power, is not meaningful and must be deleted
                # from the end of the list of marginal prices mps.
                #mps = mps(1:(mps_cnt - 1))  # marginal prices [$/kWh]
                mps.pop()
        
        
        ## A clean list of marginal prices has been created
        
        # Correct assignment of vertex power requires a small offset of any
        # duplicate values. Index through the new list of marginal prices again.
        for i in range(1, len(mps)):  #for i = 2:len(mps)
            if mps[i] == mps[i-1]:
                # A duplicate has been found. Offset the first of the two by a
                # very small number
                #mps(i - 1) = mps(i - 1) - eps  # marginal prices [$/kWh]
                mps[i-1] = mps[i-1] - (1e-10)
            
        
        ## Create vertices at the marginal prices
        # Initialize the list of vertices
        vertices = []  # Vertices
        
        # Index through the cleaned list of marginal prices
        for i in range(len(mps)):  #for i = 1:len(mps)
        
            # Create a vertex at the indexed marginal price value (See struct
            # Vertex.)
            iv = Vertex(mps[i], 0, 0)
            
            # Initialize the net power pwr and total production cost pc at the
            # indexed vertex
            pwr = 0.0  # net power [avg.kW]
            pc = 0.0  # production cost [$]
            
            ## Include power and production costs from neighbor models
            
            # Gather the list of active neighbors n
            n = mtn.neighbors  # cell array of neighbors
            
            # Index through the active neighbor models n. NOTE: Now that
            # neighbors is a cell array, its elements must be referenced using
            # curly braces.
            for k in range(len(n)):  #for k = 1:len(n)
            
                nm = n[k].model  #nm = n{k}.model  # a neighbor model
                
                if nm == ote or (hasattr(nm, 'measurementType') and not energy_type in nm.measurementType):
                
                    # The indexed neighbor model is the "object to exclude" ote.
                    # Continue without including its power or production costs.
                    continue

                # Calculate the indexed neighbor model's power at the indexed
                # marginal price and time interval. NOTE: This must not corrupt
                # the "scheduled power" at the converged system's marginal price.
                p = production(nm, mps[i], ti, energy_type=energy_type)  # power [avg.kW]
                
                # Calculate the neighbor model's production cost at the indexed
                # marginal price and time interval, and add it to the sum
                # production cost pc. NOTE: This must not corrupt the "scheduled"
                # production cost for this neighbor model.
                pc = pc + prod_cost_from_vertices(nm, ti, p, energy_type=energy_type).value
                # production cost [$]
                
                # Add the neighbor model's power to the sum net power at this
                # vertex.
                pwr = pwr + p  # net power [avg.kW]
            
            ## Include power and production costs from local asset models
            
            # Gather a list of active local assets n
            n = mtn.localAssets  # cell array of local assets
            
            # Index through the local asset models n. NOTE: now that local assets
            # is a cell array, its elements must be referenced using curly
            # braces.
            for k in range(len(n)):  #for k = 1:len(n)
            
                nm = n[k].model  #nm = n{k}.model  # a local asset model
                
                if nm == ote or (hasattr(nm, 'measurementType') and not energy_type in nm.measurementType):
                
                    # The indexed local asset model is the "object to exclude"
                    # ote. Continue without including its power or production
                    # cost.
                    continue
                
                
                # Calculate the power for the indexed local asset model at the
                # indexed marginal price and time interval.
                p = production(nm, mps[i], ti, energy_type=energy_type)  # power [avg.kW]
                
                # Find the indexed local asset model's production cost and add it
                # to the sum of production cost pc for this vertex.
                pc = pc + prod_cost_from_vertices(nm, ti, p, energy_type=energy_type).value
                # production cost [$]
                
                # Add local asset power p to the sum net power pwr for this
                # vertex.
                pwr = pwr + p  # net power [avg.kW]
            
            
            # Save the sum production cost pc into the new vertex iv
            iv.cost = pc  # sum production cost [$]
            
            # Save the net power pwr into the new vertex iv
            iv.power = pwr  # net power [avg.kW]
            
            # Append Vertex iv to the list of vertices
            vertices.append(iv)  #vertices = [vertices, iv]  # Vertices

        return vertices

    def update_costs(self, mtn):
        # Sum the production and dual costs from all modeled local resources, local
        # loads, and neighbors, and then sum them for the entire duration of the
        # time horizon being calculated.
        #
        # PRESUMPTIONS:
        # - Dual costs have been created and updated for all active time
        # intervals for all neighbor objects
        # - Production costs have been created and updated for all active time
        # intervals for all asset objects
        #
        # INTPUTS:
        # mkt - Market object
        # mtn - my Transactive Node object
        #
        # OUTPUTS:
        # - Updates Market.productionCosts - an array of total production cost in
        # each active time interval
        # - Updates Market.totalProductionCost - the sum of production costs for
        # the entire future time horizon of active time intervals
        # - Updates Market.dualCosts - an array of dual cost for each active time
        # interval
        # - Updates Market.totalDualCost - the sum of all the dual costs for the
        # entire future time horizon of active time intervals

        # Call each LocalAssetModel to update its costs
        for la in mtn.localAssets:
            la.model.update_costs(self)

        # Call each NeighborModel to update its costs
        for n in mtn.neighbors:
            n.model.update_costs(self)

        #chec for multiple energy types
        if hasattr(self, 'measurementType'):
            n_energy_types = len(self.measurementType)
        else:
            n_energy_types = 1

        for ti in self.timeIntervals:
            # Initialize the sum dual cost sdc in this time interval
            sdc = [0.0]*n_energy_types  # [$]

            # Initialize the sum production cost spc in this time interval
            spc = [0.0]*n_energy_types # [$]

            #iterate through energy types
            for i_energy_type in range(n_energy_types):
                if hasattr(self, 'measurementType'):
                    this_energy_type = self.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal

                for la in mtn.localAssets:
                    # check to see if this asset deals with this energy type
                    if this_energy_type in la.model.measurementType:
                        my_energy_type = la.model.measurementType.index(this_energy_type)
                    else:
                        continue
                    #iv = findobj(m{j}.model.dualCosts, 'timeInterval', ti[i])  # an IntervalValue
                    iv = find_obj_by_ti(la.model.dualCosts[my_energy_type], ti)
                    sdc[i_energy_type] = sdc[i_energy_type] + iv.value  # sum dual cost [$]

                    #iv = findobj(m{j}.model.productionCosts, 'timeInterval', ti[i])
                    iv = find_obj_by_ti(la.model.productionCosts[my_energy_type], ti)  # an IntervalValue
                    spc[i_energy_type] = spc[i_energy_type] + iv.value  # sum production cost [$]

                for n in mtn.neighbors:
                    # check to see if this neighbor transacts this energy type
                    if this_energy_type in n.model.measurementType:
                        my_energy_type = n.model.measurementType.index(this_energy_type)
                    else: 
                        continue
                    #iv = findobj(n{j}.model.dualCosts, 'timeInterval', ti[i])  # an IntervalValue
                    iv = find_obj_by_ti(n.model.dualCosts[my_energy_type], ti)
                    sdc[i_energy_type] = sdc[i_energy_type] + iv.value  # sum dual cost [$]

                    #iv = findobj(n{j}.model.productionCosts, 'timeInterval', ti[i])  # an IntervalValue
                    iv = find_obj_by_ti(n.model.productionCosts[my_energy_type], ti)
                    spc[i_energy_type] = spc[i_energy_type] + iv.value  # sum production cost [$]

                # Check to see if a sum dual cost exists in the indexed time interval
                #iv = findobj(mkt.dualCosts, 'timeInterval', ti[i])
                iv = find_obj_by_ti(self.dualCosts[i_energy_type], ti)

                if iv is None:  #if isempty(iv)
                    # No dual cost was found for the indexed time interval. Create
                    # an IntervalValue and assign it the sum dual cost for the
                    # indexed time interval
                    iv = IntervalValue(self, ti, self, MeasurementType.DualCost, sdc[i_energy_type])  # an IntervalValue

                    # Append the dual cost to the list of interval dual costs
                    self.dualCosts[i_energy_type].append(iv)  # = [mkt.dualCosts, iv]  # IntervalValues

                else:
                    # A sum dual cost value exists in the indexed time interval.
                    # Simply reassign its value
                    iv.value = sdc[i_energy_type]  # sum dual cost [$]

                # Check to see if a sum production cost exists in the indexed time interval
                #iv = findobj(mkt.productionCosts, 'timeInterval', ti[i])
                iv = find_obj_by_ti(self.productionCosts[i_energy_type], ti)

                if iv is None:  #if isempty(iv)
                    # No sum production cost was found for the indexed time
                    # interval. Create an IntervalValue and assign it the sum
                    # prodution cost for the indexed time interval
                    iv = IntervalValue(self, ti, self, MeasurementType.ProductionCost, spc[i_energy_type])  # an IntervalValue

                    # Append the production cost to the list of interval production costs
                    self.productionCosts[i_energy_type].append(iv)  # = [mkt.productionCosts, iv]  # IntervalValues

                else:
                    # A sum production cost value exists in the indexed time
                    # interval. Simply reassign its value
                    iv.value = spc[i_energy_type]  # sum production cost [$]
        self.totalDualCost = 0.0
        self.totalProductionCost = 0.0
        for i_energy_type in range(n_energy_types):
            # Sum total dual cost for the entire time horizon
            self.totalDualCost = self.totalDualCost + sum([x.value for x in self.dualCosts[i_energy_type]])  # [$]
            
            # Sum total primal cost for the entire time horizon
            self.totalProductionCost = self.totalProductionCost + sum([x.value for x in self.productionCosts[i_energy_type]])  # [$]

    def update_supply_demand(self, mtn):
        # FUNCTION UPDATE_SUPPLY_DEMAND()
        # For each time interval, sum the power that is generated, imported,
        # consumed, or exported for all modeled local resources, neighbors, and
        # local load.
        
        # Extract active time intervals
        ti = self.timeIntervals  # active TimeIntervals

        # update supply and demand for all power types
        if hasattr(self, 'measurementType'):
            n_power_types = len(self.measurementType)
        else:
            n_power_types = 1
        
        # Index through the active time intervals ti
        for i in range(len(ti)):  #for i = 1:len(ti)
        
            # Initialize total generation tg
            tg = [0.0]*n_power_types # [avg.kW]

            # Initialize total demand td
            td = [0.0]*n_power_types  # [avg.kW]

            ## Index through local asset models m.
            # NOTE: Now that localAssets is a cell array, its elements must be
            # referenced using curly braces.

            m = mtn.localAssets  # cell array of LocalAssets

            for k in range(len(m)):  #for k = 1:len(m)
                # if there are multiple energy types iterate through them
                if hasattr(m[k].model, 'measurementType'):
                    for j in range(len(m[k].model.measurementType)):
                        # local asset energy types must be included in the market
                        # figure out which energy type this one goes with in the market
                        i_energy_type = self.measurementType.index(m[k].model.measurementType[j])
                        # find the model scheduled power of that type
                        mo = find_obj_by_ti(m[k].model.scheduledPowers[j], ti[i])

                        # Extract and include the resource's scheduled power
                        p = mo.value  #p = mo(1).value  # [avg.kW]

                        if p > 0:  # Generation
                            # Add positive powers to total generation tg
                            tg[i_energy_type] = tg[i_energy_type] + p  # [avg.kW]

                        else:  # Demand
                            # Add negative powers to total demand td
                            td[i_energy_type] = td[i_energy_type] + p  # [avg.kW]

                # if you only have one energy type and have the legacy, non listed format, don't iterate
                else:
                    #mo = findobj(m{k}.model.scheduledPowers, 'timeInterval', ti[i])  # IntervalValues
                    mo = find_obj_by_ti(m[k].model.scheduledPowers, ti[i])

                    # Extract and include the resource's scheduled power
                    p = mo.value  #p = mo(1).value  # [avg.kW]

                    if p > 0:  # Generation
                        # Add positive powers to total generation tg
                        tg = tg + p  # [avg.kW]

                    else:  # Demand
                        # Add negative powers to total demand td
                        td = td + p  # [avg.kW]

            ## Index through neighbors m
            m = mtn.neighbors  # cell array of Neighbors

            for k in range(len(m)):  #for k = 1:len(m)
                # if there are multiple energy types iterate through them
                if hasattr(m[k].model, 'measurementType'):
                    for j in range(len(m[k].model.measurementType)):
                        # find which energy type the neighbor is using
                        # a neighbor node may have an energy type that is not transacted with this node
                        if m[k].model.measurementType[j] in self.measurementType:
                            i_energy_type = self.measurementType.index(m[k].model.measurementType[j])
                            # find the model scheduled power of that type
                            mo = find_obj_by_ti(m[k].model.scheduledPowers[j], ti[i])

                            # Extract and include the resource's scheduled power
                            p = mo.value  #p = mo(1).value  # [avg.kW]

                            if p > 0:  # Generation
                                # Add positive powers to total generation tg
                                tg[i_energy_type] = tg[i_energy_type] + p  # [avg.kW]

                            else:  # Demand
                                # Add negative powers to total demand td
                                td[i_energy_type] = td[i_energy_type] + p  # [avg.kW]
                
                # if you only have a single energy type and are using the legacy non-list format, don't iterate
                else:
                    # Find scheduled power for this neighbor in the indexed time interval
                    #mo = findobj(m{k}.model.scheduledPowers, 'timeInterval', ti[i])
                    mo = find_obj_by_ti(m[k].model.scheduledPowers, ti[i])

                    # Extract and include the neighbor's scheduled power
                    p = mo.value  #p = mo(1).value  # [avg.kW]

                    if p > 0:  # Generation
                        # Add positive power to total generation tg
                        tg = tg + p  # [avg.kW]

                    else:  # Demand
                        # Add negative power to total demand td
                        td = td + p  # [avg.kW]

            # At this point, total generation and importation tg, and total
            # demand and exportation td have been calculated for the indexed
            # time interval ti[i]

            # Save the total generation in the indexed time interval
            # if there are multiple energy types, iterate through them to save
            if len(self.measurementType)>0:
                for i_energy_type in range(len(self.measurementType)):
                    #check whether the total generation exists for the indexed time interval of this energy type
                    totalGen = self.totalGeneration[:] #clone this to avoid aliasing the total generation
                    iv = find_obj_by_ti(self.totalGeneration[i_energy_type], ti[i])

                    if iv is None:
                        iv = IntervalValue(self, ti[i], self, MeasurementType.TotalGeneration, tg[i_energy_type])
                        self.totalGeneration[i_energy_type].append(iv)

                    else:
                        # the total generation exists, so overwrite its value
                        iv.value = tg[i_energy_type]

                    # check whether the total demand exists for the indexed time interval of this energy type
                    iv = find_obj_by_ti(self.totalDemand[i_energy_type], ti[i])

                    if iv is None:
                        iv = IntervalValue(self, ti[i], self, MeasurementType.TotalDemand, td[i_energy_type])
                        self.totalDemand[i_energy_type].append(iv)

                    else:
                        # the total demand exists, so overwrite its value
                        iv.value = td[i_energy_type]

                    iv = find_obj_by_ti(self.netPowers[i_energy_type], ti[i])

                    if iv is None:
                        iv = IntervalValue(self, ti[i], self, MeasurementType.NetPower, tg[i_energy_type] + td[i_energy_type])
                        self.netPowers[i_energy_type].append(iv)
                    
                    else:
                        # the net demand exists, so overwrite its value
                        iv.value = tg[i_energy_type] + td[i_energy_type]
                        

            # if there is only one energy type, no need for iterating through them
            else:
                # Check whether total generation exists for the indexed time interval
                #iv = findobj(mkt.totalGeneration, 'timeInterval', ti[i])  # an IntervalValue
                iv = find_obj_by_ti(self.totalGeneration, ti[i])

                if iv is None:  #if isempty(iv)

                    # No total generation was found in the indexed time interval.
                    # Create an interval value.
                    iv = IntervalValue(self, ti[i], self, MeasurementType.TotalGeneration, tg)  # an IntervalValue

                    # Append the total generation to the list of total generations
                    self.totalGeneration.append(iv)  #mkt.totalGeneration = [mkt.totalGeneration, iv]

                else:

                    # Total generation exists in the indexed time interval. Simply
                    # reassign its value.
                    iv.value = tg  #iv(1).value = tg  # [avg.kW]

                ## Calculate and save total demand for this time interval.
                # NOTE that this formulation includes both consumption and
                # exportation among total load.

                # Check whether total demand exists for the indexed time
                # interval

                #iv = findobj(mkt.totalDemand, 'timeInterval', ti[i])  # an IntervalValue
                iv = find_obj_by_ti(self.totalDemand, ti[i])

                if iv is None:  #if isempty(iv)

                    # No total demand was found in the indexed time interval. Create
                    # an interval value.
                    iv = IntervalValue(self, ti[i], self, MeasurementType.TotalDemand, td)  # an IntervalValue

                    # Append the total demand to the list of total demands
                    self.totalDemand.append(iv)  #mkt.totalDemand = [mkt.totalDemand, iv]

                else:

                    # Total demand was found in the indexed time interval. Simply
                    # reassign it.
                    iv.value = td  #iv(1).value = td  # [avg.kW]

                ## Update net power for the interval
                # Net power is the sum of total generation and total load.
                # By convention generation power is positive and consumption
                # is negative.

                # Check whether net power exists for the indexed time interval
                #iv = findobj(mkt.netPowers, 'timeInterval', ti[i])  # an IntervalValue
                iv = find_obj_by_ti(self.netPowers, ti[i])

                if iv is None:  #if isempty(iv)

                    # Net power is not found in the indexed time interval. Create an
                    # interval value.
                    iv = IntervalValue(self, ti[i], self, MeasurementType.NetPower, tg + td)  # an IntervalValue

                    # Append the net power to the list of net powers
                    self.netPowers.append(iv)  #mkt.netPowers = [mkt.netPowers, iv]  # [avg.kW]

                else:

                    # A net power was found in the indexed time interval. Simply
                    # reassign its value.
                    iv.value = tg + td  #iv(1).value = tg + td  # [avg.kW]

    def view_marginal_prices(self, energy_type = MeasurementType.PowerReal):
        import matplotlib.pyplot as plt

        
        # Gather active time series and make sure they are in chronological order
        ti = self.timeIntervals
        ti = [x.startTime for x in ti]  #ti = [ti.startTime]
        ti.sort()  #ti = sort(ti)

        # if there are multiple energy types being handled, find the correct one
        if hasattr(self, 'measurementType'):
            i_energy_type = self.measurementType.index(energy_type)
        else:
            i_energy_type = -1
        
        #if ~isa(mkt, 'Market')
        if not isinstance(self, Market):  # if ~isa(tnm, 'NeighborModel')
            _log.warning('Object must be a NeighborModel or LocalAssetModel')
            return
        else:
            mp = self.marginalPrices

        #mp_ti = [x.timeInterval for x in mp]  #mp_ti = [mp.timeInterval]
        #[~, ind] = sort([mp_ti.startTime])
        #mp = mp(ind)
        #mp = [mp.value]
        if i_energy_type>=0:
            sorted_mp = sorted(mp[i_energy_type], key=lambda x: (x.timeInterval.startTime))
        else:
            sorted_mp = sorted(mp, key=lambda x: (x.timeInterval.startTime))
        mp = [x.value for x in sorted_mp]


        # This can be made prettier as time permits.
        fig = plt.figure()
        ax = plt.axes()

        ax.plot(ti, mp)
        plt.title('Marginal Prices in Active Time Intervals')
        plt.xlabel('time')
        plt.ylabel('marginal price ($/kWh)')

    def view_net_curve(self, i, energy_type=MeasurementType.PowerReal):
        """
        Not completed
        :param i:
        :return:
        """
        import matplotlib.pyplot as plt

        # VIEW_MARGINAL_PRICES() - visualize marginal pricing in active time
        # intervals.
        # mkt - market object

        # Gather active time series and make sure they are in chronological order
        ti = self.timeIntervals
        ti_objs = sort_vertices(ti, 'startTime')
        ti = [x.startTime for x in ti]  # ti = [ti.startTime]
        ti.sort()  # ti = sort(ti)

        # if there are multiple energy types, find the index for this one
        if hasattr(self, 'measurementType') and (energy_type in self.measurementType):
            i_energy_type = self.measurementType.index(energy_type)
        else:
            i_energy_type = -1

        # if ~isa(mkt, 'Market')
        if not isinstance(self, Market):
            _log.warning('Object must be a NeighborModel or LocalAssetModel')
            return
        else:
            mp = self.marginalPrices

        # mp_ti = [x.timeInterval for x in mp]  #mp_ti = [mp.timeInterval]
        # [~, ind] = sort([mp_ti.startTime])
        # mp = mp(ind)
        # mp = [mp.value]
        if i_energy_type>=0:
            sorted_mp = sorted(mp[i_energy_type], key=lambda x: x.timeInterval.startTime)
        else:
            _log.warning('This Market does not transact energy type '+ str(energy_type))
            return
            #sorted_mp = sorted(mp, key=lambda x: x.timeInterval.startTime)
        mp = [x.value for x in sorted_mp]

        # This can be made prettier as time permits.
        fig = plt.figure()
        ax = plt.axes()

        #ax.plot(ti, mp)
        plt.title('Marginal Prices in Active Time Intervals')
        plt.xlabel('time')
        plt.ylabel('marginal price ($/kWh)')

        # Pick out the active time interval that is indexed by input i
        ti_objs = ti_objs[i]
        
        # Find the active system vertices in the indexed time interval
        #vertices = findobj(mkt.activeVertices, 'timeInterval', ti)  # IntervalValues
        if i_energy_type>=0:
            vertices = find_objs_by_ti(self.activeVertices[i_energy_type], ti_objs)
        else:
            vertices = find_objs_by_ti(self.activeVertices, ti_objs)
        
        # Extract the vertices. See struct Vertex.
        vertices = [x.value for x in vertices]  #vertices = [vertices.value]  # active Vertices
        
        # Eliminate any vertices that have infinite marginal price values
        #ind = ~isinf([vertices.marginalPrice])  # an index array
        #vertices = vertices(ind)  # Vertices
        #vertices = [x for x in vertices if x.marginalPrice != float("inf")]
        
        # Sort the active vertices in the indexed time interval by power and by
        # marginal price
        vertices = order_vertices(vertices)  # Vertices
        
        # Calculate the extremes and range of the horizontal marginal-price axis
        x = [x.marginalPrice for x in vertices]
        minx = min(x)  # min([vertices.marginalPrice])  # [$/kWh]
        maxx = max(x)  # max([vertices.marginalPrice])  # [$/kWh]
        xrange = maxx - minx  # [$/kWh]
        if maxx==float('inf') and minx==float('inf'): # in case all marginal prices are inf, still plot to show the power demand
            minx = 0
            xrange = 1
        
        # Calculate the extremes and range of the vertical power axis
        y = [x.power for x in vertices]
        miny = min(y)  # min([vertices.power])  # avg.kW]
        maxy = max(y)  # max([vertices.power])  # avg.kW]
        yrange = maxy - miny  # avg.kW]
        if yrange == 0:
            yrange = 2
        
        # Perform scaling if power range is large
        if yrange > 1000:
            unit = '(MW)'
            factor = 0.001
            miny = factor * miny
            maxy = factor * maxy
            yrange = factor * yrange
        else:
            unit = '(kW)'
            factor = 1.0

        # Start the figure with nicely scaled axes
        #axis([minx - 0.1 * xrange, maxx + 0.1 * xrange, miny - 0.1 * yrange, maxy + 0.1 * yrange])

        
        # Place a marker at each vertex.
        #plot([vertices.marginalPrice], factor * [vertices.power], '*')
        
        # Create a horizontal line at zero.
        #line([minx - 0.1 * xrange, maxx + 0.1 * xrange], [0.0, 0.0], 'LineStyle', '--')
        plt.plot([minx - 0.1 * xrange, maxx + 0.1 * xrange],
                 [0.0, 0.0])

        # Draw a line from the left figure boundary to the first vertex.
        if vertices[0].marginalPrice == float('inf'):
            plt.plot([minx - 0.1 * xrange, 5],
                [factor * vertices[0].power, factor * vertices[0].power])
        else:
            #line([minx - 0.1 * xrange, vertices(1).marginalPrice], [factor * vertices(1).power, factor * vertices(1).power])
            plt.plot([minx - 0.1 * xrange, vertices[0].marginalPrice],
                    [factor * vertices[0].power, factor * vertices[0].power])

            # Draw lines from each vertex to the next. If two successive
            # vertices are not continuous, no line should be drawn.
            for i in range(len(vertices)-1):  #for i = 1:(len(vertices) - 1)
                linestyle = ''
                if vertices[i].continuity == 0 and vertices[i+1].continuity == 0:
                    #line([vertices(i:i + 1).marginalPrice], factor * [vertices(i:i + 1).power], 'LineStyle', 'none')
                    linestyle = ''
                else:
                    #line([vertices(i:i + 1).marginalPrice], factor * [vertices(i:i + 1).power], 'LineStyle', '-')
                    linestyle = '-'

                plt.plot([vertices[i].marginalPrice, vertices[i + 1].marginalPrice],
                        [factor * vertices[i].power, factor * vertices[i + 1].power],
                        linestyle=linestyle)
            
            # Draw a line from the rightmost vertex to the left figure boundary.
            #len = len(vertices)
            #line([vertices(len).marginalPrice, maxx + 0.1 * xrange], [factor * vertices(len).power, factor * vertices(len).power])
            plt.plot([vertices[-1].marginalPrice, maxx + 0.1 * xrange],
                    [factor * vertices[-1].power, factor * vertices[-1].power],
                    linestyle=linestyle)


        # Pretty it up with labels and title
        #ax.plot(ti, mp)
        plt.title('Production Vertices (' + ti_objs.name + ')')
        plt.xlabel('unit price ($/kWh)')
        plt.ylabel('power ' + str(unit))
        plt.show()
