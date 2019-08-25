import logging
#utils.setup_logging()
_log = logging.getLogger(__name__)

from model import Model
from vertex import Vertex
from interval_value import IntervalValue
from measurement_type import MeasurementType
from helpers import *
from market import Market
from time_interval import TimeInterval
from local_asset import LocalAsset


class LocalAssetModel(Model, object):
    # LocalAssetModel Base Class
    # A local asset model manages and represents a local asset object,
    # meaning that it
    # (1) determines a power schedule across all active time intervals,
    # (2) calculates costs that are needed by system optimization, and
    # (3) models flexibility, if any, that is available from the control of
    # this asset in active time intervals.
    #
    # This base class provides many of the properties and methods that will
    # be needed to manage local assets--generation and demand alike. However,
    # it schedules only the simplest, constant power throughout active time
    # intervals. Subclassing will be required to perform dynamic power
    # scheduling, expecially where scheduling is highly constrained or
    # invokes optimizations. Even then, implementers might need further
    # subclassing to model their unique assets.
    #
    # Available subclasses that inherit from this base class: (This taxonomy
    # is influenced by the thesis (Kok 2013).
    # Inelastic - dynamic scheduling independent of prices
    # Shiftable - schedule a fixed utility over a time range
    # Buffering - schedule power while managing a (thermal) buffer
    # Storage - optimize revenue, less cost
    # Controllable - unconstrained scheduling based on a polynomial
    #  production or utility def

    def __init__(self, energy_types=[MeasurementType.PowerReal]):
        super(LocalAssetModel, self).__init__()
        self.activeVertices = [[] for et in energy_types]
        self.defaultPower = [0.0]*len(energy_types)  # [avg. kW]
        self.engagementCost = [0.0, 0.0, 0.0]  # [engagement, hold, disengagement][$]
        self.engagementSchedule = [[] for et in energy_types]  # IntervalValue.empty
        self.informationServices = []  # InformationService.empty
        self.measurementType = energy_types
        self.productionCosts = [[] for et in energy_types]
        self.dualCosts = [[] for et in energy_types]
        self.reserveMargins = [[] for et in energy_types]
        self.scheduledPowers = [[] for et in energy_types]
        self.transitionCosts = [[] for et in energy_types] # IntervalValue.empty  # values are [$]

    def cost(self, p):
        # def COST()
        # Calculate production (consumption) cost at the given power level.
        #
        # INPUTS:
        # obj - class object for which the production costs are to be
        # calculated
        # p - power production (consumption) for which production
        # (consumption) costs are to be calculated [kW]. By convention,
        # imported and generated power is positive exported or consumed
        # power is negative.
        #
        # OUTPUTS:
        # pc - calculated production (consumption) cost [$/h]
        #
        # LOCAL:
        # a - array of production cost coefficients that must be ordered [a0
        # a1 a2], such that cost = a0 + a1*p + a2*p^2 [$/h].
        # *************************************************************************

        # Extract the production cost coefficients for the given object

        a = self.cost_parameters

        # Calculate the production (consumption) cost for the given power

        pc = a[0] + a[1] * p + a[2] * p ** 2  # [$/h]

        return pc

    ## SEALED - DONOT MODIFY
    ## schedule() - have object schedule its power in active time intervals
    def schedule(self, mkt):
        # But give power scheduling priority for a LocalAssetModel
        self.schedule_power(mkt)
        self.schedule_engagement(mkt)  # only LocalAssetModels
        self.update_vertices(mkt)

        # Have the objects estimate their available reserve margin
        self.calculate_reserve_margin(mkt)

    def schedule_power(self, mkt):
        # def SCHEDULE_POWER() - determine powers of an asset in active time
        # intervals. NOTE that this method may be redefined by subclasses if more
        # features are needed. NOTE that this method name is common for all asset
        # and neighbor models to facilitate its redefinition.
        #
        # PRESUMPTIONS:
        # - Active time intervals exist and have been updated
        # - Marginal prices exist and have been updated. NOTE: Marginal prices
        #   are not used for inelastic assets.
        # - Transition costs, if relevant, are applied during the scheduling
        #   of assets.
        # - An engagement schedule, if used, is applied during an asset's power
        #   scheduling.
        # - Scheduled power and engagement schedule must be self consistent at
        # the end of this method. That is, power should not be scheduled while
        # the asset is disengaged (uncommitted).
        #
        # INPUTS:
        # obj - local asset model object
        # mkt - market object
        #
        # OUTPUTS:
        # - Updates self.scheduledPowers - the schedule of power consumed
        # - Updates self.engagementSchedule - an array that states whether the
        #   asset is engaged (committed) (true) or not (false) in the time
        #   interval

        # Gather the active time intervals ti
        ti = mkt.timeIntervals  # active TimeIntervals

        # Gather the energy type information
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Index through the active time intervals ti
        for i in range(len(ti)):  # for i = 1:len(ti):
            # index by energy type
            for i_energy_type in range(n_energy_types):
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal

                # if this local asset has that energy type
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                # if this local asset doesn't have that energy type, move on to the next one
                else:
                    continue
                # Check whether a scheduled power already exists for the indexed time interval
                #iv = findobj(self.scheduledPowers, 'timeInterval', ti(i))
                iv = find_obj_by_ti(self.scheduledPowers[my_energy_type], ti[i])

                if iv is None:

                    # A scheduled power does not exist for the indexed time
                    # interval.

                    # Create the scheduled power from its default. NOTE this simple
                    # method must be replaced if more model features are needed.
                    val = self.defaultPower[my_energy_type]  # [avg.kW]

                    # Create an interval value and assign the default value
                    #iv = IntervalValue(obj, ti(i), mkt, 'ScheduledPower', val)
                    iv = IntervalValue(self, ti[i], mkt, MeasurementType.ScheduledPower, val)  # an IntervalValue

                    # Append the new scheduled power to the list of scheduled
                    # powers for the active time intervals
                    #self.scheduledPowers = [self.scheduledPowers, iv]  # IntervalValues
                    self.scheduledPowers[my_energy_type].append(iv)

                else:

                    # The scheduled power already exists for the indexed time
                    # interval. Simply reassign its value
                    iv.value = self.defaultPower[my_energy_type]  # [avg.kW]

            # Remove any extra scheduled powers
            #xsp = ismember([self.scheduledPowers.timeInterval], ti)
            # an array of logicals
            #self.scheduledPowers = self.scheduledPowers(xsp)  # IntervalValues
            self.scheduledPowers[my_energy_type] = [x for x in self.scheduledPowers[my_energy_type] if x.timeInterval in ti]

    def schedule_engagement(self, mkt):
        # SCHEDULE_ENGAGEMENT - method to assign engagement, or committment, which
        # is relevant to some local assets (supports future capabilities).
        # NOTE: The assignment of engagement schedule, if used, may be assigned
        # during the scheduling of power, not separately as demonstrated here.
        # Committment and engagement are closely aligned with the optimal
        # production costs of schedulable generators and utility def of
        # engagements (e.g., demand responses).

        # NOTE: Because this is a future capability, Implementers might choose to
        # simply return from the call until LocalAsset behaviers are found to need
        # committment or engagement.
        # return

        # Gather the active time intervals ti
        ti = mkt.timeIntervals  # active TimeIntervals

        # gather information on different energy types
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Index through the active time intervals ti
        for i in range(len(ti)):  # for i = 1:len(ti):
            # index through energy types
            for i_energy_type in range(n_energy_types):
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal

                # if this local asset has that energy type, then schedule assets
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                # if this local asset does not have that energy type, move on to the next one
                else:
                    continue
                # Check whether an engagement schedule exists in the indexed time
                # interval
                #iv = findobj(self.engagementSchedule, 'timeInterval', ti(i))
                iv = find_obj_by_ti(self.engagementSchedule[my_energy_type], ti[i])

                # NOTE: this template currently assigns engagement value as true
                # (i.e., engaged).
                val = True  # Asset is committed or engaged
        
                if iv is None:
        
                    # No engagement schedule was found in the indexed time interval.
                    # Create an interval value and assign its value.
                    #iv = IntervalValue(obj, ti(i), mkt, 'EngagementSchedule', val)
                    iv = IntervalValue(self, ti[i], mkt, MeasurementType.EngagementValue, val)
                    # an IntervalValue
        
                    # Append the interval value to the list of active interval
                    # values
                    #self.engagementSchedule = [self.engagementSchedule, iv]
                    self.engagementSchedule[my_energy_type].append(iv)  # IntervalValues
        
                else:
        
                    # An engagement schedule was found in the indexed time interval.
                    # Simpy reassign its value.
                    iv.value = val  # [$]


            # Remove any extra engagement schedule values
            #xes = ismember([self.engagementSchedule.timeInterval], ti)
            # an array of logicals
            #self.engagementSchedule = self.engagementSchedule(xes)  # IntervalValues
            self.engagementSchedule[my_energy_type] = [x for x in self.engagementSchedule[my_energy_type] if x.timeInterval in ti]

    def calculate_reserve_margin(self, mkt):
        # def CALCULATE_RESERVE_MARGIN() - Estimate available (spinning)
        # reserve margin for this asset.
        #
        # NOTES:
        #   This method works with the simplest base classes that have constant
        #   power and therefore provide no spinning reserve. This method may be
        #   redefined by subclasses of the local asset model to add new features
        #   or capabilities.
        #   This calculation will be more meaningful and useful after resource
        #   commitments and uncertainty estimates become implemented. Until then,
        #   reserve margins may be tracked, even if they are not used.
        #
        # PRESUMPTIONS:
        # - Active time intervals exist and have been updated
        # - The asset's maximum power is a meaningful and accurate estimate of
        #   the maximum power level that can be achieved on short notice, i.e.,
        #   spinning reserve.
        #
        # INPUTS:
        # obj - local asset model object
        # mkt - market object
        #
        # OUTPUTS:
        # Modifies self.reserveMargins - an array of estimated (spinning) reserve
        # margins in active time intervals

        # Gather the active time intervals ti
        ti = mkt.timeIntervals  # active TimeIntervals

        # Gather energy types
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Index through active time intervals ti
        for i in range(len(ti)):  # for i = 1:len(ti):
            # index through energy types
            for i_energy_type in range(n_energy_types):
                # check to see if you have this format
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal
                # check to see if this local asset deals with that energy type
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                else:
                    continue

                # Calculate the reserve margin for the indexed interval. This is the
                # non-negative difference between the maximum asset power and the
                # scheduled power. In principle, generation may be increased or
                # demand decreased by this quantity to act as spinning reserve.

                # Find the scheduled power in the indexed time interval
                #iv = findobj(obj.scheduledPowers, 'timeInterval', ti(i))
                iv = find_obj_by_ti(self.scheduledPowers[my_energy_type], ti[i])

                # Calculate the reserve margin rm in the indexed time interval. The
                # reserve margin is the differnce between the maximum operational
                # power value in the interval and the scheduled power. The
                # operational maximum should be less than the object's hard physical
                # power constraint, so a check is in order.
                # start with the hard physical constraint.
                hard_const = self.object.maximumPower[my_energy_type]  # [avg.kW]

                # Calculate the operational maximum constraint, which is the highest
                # point on the supply/demand curve (i.e., the vertex) that represents
                # the residual flexibility of the asset in the time interval.
                #op_const = findobj(obj.activeVertices, 'timeInterval', ti(i))
                op_const = find_objs_by_ti(self.activeVertices[my_energy_type], ti[i])  # IntervalValues

                if len(op_const) == 0:  #if isempty(op_const)
                    op_const = hard_const
                else:
                    op_const = [x.value for x in op_const]  # active vertices
                    op_const = max([x.power for x in op_const])  # operational max. power[avg.kW]

                # Check that the upper operational power constraint is less than or
                # equal to the object's hard physical constraint.
                soft_maximum = min(hard_const, op_const)  # [avg.kW]

                # And finally calculate the reserve margin.
                #rm = max(0, soft_maximum - iv(1).value)  # reserve margin [avg. kW]
                rm = max(0, soft_maximum - iv.value)  # reserve margin [avg. kW]

                # Check whether a reserve margin already exists for the indexed
                # time interval
                #iv = findobj(obj.reserveMargins, 'timeInterval', ti(i))
                iv = find_obj_by_ti(self.reserveMargins[my_energy_type], ti[i])  # an IntervalValue

                if iv is None:

                    # A reserve margin does not exist for the indexed time interval.
                    # create it. (See IntervalValue class.)
                    #iv = IntervalValue(obj, ti(i), mkt, 'ReserveMargin', rm)
                    iv = IntervalValue(self, ti[i], mkt, MeasurementType.ReserveMargin, rm)  # an IntervalValue

                    # Append the new reserve margin interval value to the list of
                    # reserve margins for the active time intervals
                    #self.reserveMargins = [self.reserveMargins, iv]  # IntervalValues
                    self.reserveMargins[my_energy_type].append(iv)
                else:
                    # The reserve margin already exists for the indexed time
                    # interval. Simply reassign its value.
                    #iv(1).value = rm  # reserve margin [avg.kW]
                    iv.value = rm

    def engagement_cost(self, dif):
        # def ENGAGEMENT_COST() - assigns engagement cost based on difference
        # in engagement status in the current minus prior time intervals.
        #
        # INPUTS:
        # obj - local asset model object
        # dif - difference (current interval engagement - prior interval
        #  engagement), which assumes integer values [-1,0,1] that should
        #  correspond to the three engagement costs.
        # USES:
        # self.engagementSchedule
        # self.engagementCost
        #
        # OUTPUTS:
        # cost - transition cost
        # diff - cost table as a def of current and prior engagement states:
        #   \ current |   false   |  true
        # prior false   |  0:ec(2)  | 1:ec(3)
        # true    | -1:ec(1)  | 0:ec(2)

        # Check that dif is a feasible difference between two logical values
        if not dif in [-1, 0, 1]:
            print('Input value must be in the set {-1,0,1}.')
            return


        # Assign engagement cost by indexing the three values of engagement cost
        # 1 - transition from false to true - engagement cost
        # 2 - no change in engagemment - no cost
        # 3 - transition from true to false - disengagment cost
        #cost = self.engagementCost(2 + dif)  # [$]
        cost = self.engagementCost[1+dif]  # python 0-based vs. matlab

        return cost

    def assign_transition_costs(self, mkt):
        # def ASSIGN_TRANSITION_COSTS() - assign the cost of changeing
        # engagement state from the prior to the current time interval
        #
        # PRESUMPTIONS:
        # - Time intervals exist and have been updated
        # - The engagement schedule exists and has been updated. Contents are
        #   logical [true/false].
        # - Engagement costs have been accurately assigned for [disengagement,
        #   unchanged, engagement]
        #
        # INPUTS:
        # obj - Local asset model object
        # mkt - Market object
        #
        # USES:
        # - self.engagementCost - three costs that correspond to
        #   [disengagement, unchanged, engagement) transitions
        # - self.engagement_cost() - assigns appropriate cost from
        #   self.engagementCost property
        # - self.engagementSchedule - engagement states (true/false) for the asset
        #   in active time intervals
        #
        # OUTPUTS:
        # Assigns values to self.transition_costs

        # Gather active time intervals
        ti = mkt.timeIntervals  # TimeIntervals

        #gather information on energy types
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Ensure that ti is ordered by time interval start times
        #[~, ind] = sort([ti.startTime])  # logical array
        #ti = ti(ind)
        ti.sort(key=lambda x: x.startTime)

        # Index through all but the first time interval ti
        for i in range(1, len(ti)):  # for i = 2:len(ti):
            # index through all the energy types
            for i_energy_type in range(n_energy_types):
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal
                # check to see if this local asset deals with that energy type
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                else:
                    continue

                # Find the current engagement schedule ces in the current indexed
                # time interval ti(i)
                #ces = findobj(self.engagementSchedule, 'timeInterval', ti(i))
                ces = [x for x in self.engagementSchedule[my_energy_type] if x.timeInterval == ti[i]]

                # Extract its engagement state
                ces = ces[0].value  # logical (true/false)

                # Find the engagement schedule pes in the prior indexed time interval
                # ti(i-1)
                #pes = findobj(self.engagementSchedule, 'timeInterval', ti(i - 1))
                pes = [x for x in self.engagementSchedule[my_energy_type] if x.timeInterval == ti[i-1]]

                # And extract its value
                pes = pes[0].value  # logical (true/false)

                # Calculate the state transition
                # - -1:Disengaging
                # -  0:Unchaged
                # -  1:Engaging
                dif = ces - pes  # in {-1,0,1}

                # Assign the corresponding transition cost
                val = self.engagement_cost(dif)

                # Check whether a transition cost exists in the indexed time interval
                #iv = findobj(self.transitionCosts, 'timeInterval', ti(i))
                iv = find_obj_by_ti(self.transitionCosts[my_energy_type], ti[i])

                if iv is None:

                    # No transition cost was found in the indexed time interval.
                    # Create an interval value and assign its value.
                    #iv = IntervalValue(obj, ti(i), mkt, 'TransitionCost', val)
                    iv = IntervalValue(self, ti[i], mkt, MeasurementType.TransitionCost, val)
                    # an IntervalValue

                    # Append the interval value to the list of active interval
                    # values
                    #self.transitionCosts = [self.transitionCosts, iv]  # IntervalValues
                    self.transitionCosts[my_energy_type].append(iv)

                else:

                    # A transition cost was found in the indexed time interval.
                    # Simpy reassign its value.
                    iv.value = val  # [$]

        for my_energy_type in range(len(self.measurementTypes)):
            # Remove any extraneous transition cost values
            #aes = ismember([self.transitionCosts.timeInterval], ti)  # logical array
            #self.transitionCosts = self.transitionCosts(aes)  # active IntervalValues
            self.transitionCosts[my_energy_type] = [x for x in self.transitionCosts[my_energy_type] if x.timeInterval in ti]

    def update_dual_costs(self, mkt):
        # UPDATE_DUAL_COSTS() - Update the dual cost for all active time intervals
        # (NOTE: Choosing not to separate this def from the base class because
        # cost might need to be handled differently and redefined in subclasses.)

        # Gather the active time intervals ti
        ti = mkt.timeIntervals  # active TimeIntervals

        # gather information on energy types
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Index through the time intervals ti
        for i in range(len(ti)):  # for i = 1:len(ti):
            # index through the energy types in the market
            for i_energy_type in range(n_energy_types):
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal
                # check to see if this local asset has that energy type
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                else:
                    continue

                # Find the marginal price mp for the indexed time interval ti(i) in
                # the given market mkt
                #mp = findobj(mkt.marginalPrices, 'timeInterval', ti(i))
                mp = find_obj_by_ti(mkt.marginalPrices[i_energy_type], ti[i])
                mp = mp.value  # a marginal price [$/kWh]

                # Find the scheduled power sp for the asset in the indexed time interval ti(i)
                #sp = findobj(self.scheduledPowers, 'timeInterval', ti(i))
                sp = find_obj_by_ti(self.scheduledPowers[my_energy_type], ti[i])
                sp = sp.value  # schedule power [avg.kW]

                # Find the production cost in the indexed time interval
                #pc = findobj(self.productionCosts, 'timeInterval', ti(i))
                pc = find_obj_by_ti(self.productionCosts[my_energy_type], ti[i])
                pc = pc.value  # production cost [$]

                # Dual cost in the time interval is calculated as production cost,
                # minus the product of marginal price, scheduled power, and the
                # duration of the time interval.
                #dc = pc - (mp * sp * hours(ti(i).duration))  # a dual cost [$]
                dur = ti[i].duration.seconds//3600
                dc = pc - (mp * sp * dur)  # a dual cost [$]

                # Check whether a dual cost exists in the indexed time interval
                #iv = findobj(self.dualCosts, 'timeInterval', ti(i))  # an IntervalValue
                iv = find_obj_by_ti(self.dualCosts[my_energy_type], ti[i])
                
                if iv is None:

                    # No dual cost was found in the indexed time interval. Create an
                    # interval value and assign it the calculated value.
                    #iv = IntervalValue(obj, ti(i), mkt, 'DualCost', dc)
                    iv = IntervalValue(self, ti[i], mkt, MeasurementType.DualCost, dc)  # an IntervalValue

                    # Append the new interval value to the list of active interval
                    # values
                    #self.dualCosts = [self.dualCosts, iv]  # IntervalValues
                    self.dualCosts[my_energy_type].append(iv)

                else:

                    # The dual cost value was found to already exist in the indexed
                    # time interval. Simply reassign it the new calculated value.
                    iv.value = dc  # a dual cost [$]
        
        self.totalDualCost = 0.0
        for my_energy_type in range(len(self.measurementType)):

            # Ensure that only active time intervals are in the list of dual costs
            # adc
            #adc = ismember([self.dualCosts.timeInterval], ti)  # a logical array
            #self.dualCosts = self.dualCosts(adc)  # IntervalValues
            self.dualCosts[my_energy_type] = [x for x in self.dualCosts[my_energy_type] if x.timeInterval in ti]

            # Sum the total dual cost and save the value
            # self.totalDualCost = sum([self.dualCosts.value])  # total dual cost [$]
            self.totalDualCost = self.totalDualCost + sum([x.value for x in self.dualCosts[my_energy_type]])

    def update_production_costs(self, mkt):
        # UPDATE_PRODUCTION_COSTS() - Calculate the costs of generated energies.
        # (NOTE: Choosing not to separate this def from the base class because
        # cost might need to be handled differently and redefined in subclasses.)

        # Gather active time intervals ti
        ti = mkt.timeIntervals  # active TimeIntervals

        # gather energy type information
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Index through the active time interval ti
        for i in range(len(ti)):  # for i = 1:len(ti):
            # index through the energy types
            for i_energy_type in range(n_energy_types):
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal
                # check to see if this local asset deals with that energy type
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                # if this local asset does not have this energy type, move on to the next one
                else:
                    continue

                # Get the scheduled power sp in the indexed time interval
                #sp = findobj(self.scheduledPowers, 'timeInterval', ti(i))
                sp = find_obj_by_ti(self.scheduledPowers[my_energy_type], ti[i])
                sp = sp.value  # schedule power [avg.kW]

                # Call on def that calculates production cost pc based on the
                # vertices of the supply or demand curve
                # NOTE that this def is now stand-alone because it might be
                # generally useful for a number of models.
                pc = prod_cost_from_vertices(self, ti[i], sp, energy_type=this_energy_type, market=mkt)  # interval production cost [$]
                pc = pc.value

                # Check for a transition cost in the indexed time interval.
                # (NOTE: this differs from neighbor models, which do not posses the
                # concept of commitment and engagement. This is a good reason to keep
                # this method within its base class to allow for subtle differences.)
                #tc = findobj(self.transitionCosts, 'timeInterval', ti(i))
                tc = find_obj_by_ti(self.transitionCosts[my_energy_type], ti[i])
                
                if tc is None:
                    tc = 0.0  # [$]
                else:
                    tc = tc.value  # [$]

                # Add the transition cost to the production cost
                pc = pc + tc

                # Check to see if the production cost value has been defined for the
                # indexed time interval
                #iv = findobj(self.productionCosts, 'timeInterval', ti(i))
                iv = find_obj_by_ti(self.productionCosts[my_energy_type], ti[i])

                if iv is None:
                    # The production cost value has not been defined in the indexed
                    # time interval. Create it and assign its value pc.
                    #iv = IntervalValue(obj, ti(i), mkt, 'ProductionCost', pc)
                    iv = IntervalValue(self, ti[i], mkt, MeasurementType.ProductionCost, pc)

                    # Append the production cost to the list of active production
                    # cost values
                    self.productionCosts[my_energy_type].append(iv)  # IntervalValues

                else:

                    # The production cost value already exists in the indexed time
                    # interval. Simply reassign its value.
                    iv.value = pc  # interval production cost [$]

        self.totalProductionCost = 0.0
        for my_energy_type in range(len(self.measurementType)):
            # Ensure that only active time intervals are in the list of active
            # production costs apc
            #apc = ismember([self.productionCosts.timeInterval], ti)  # a logical array
            #self.productionCosts = self.productionCosts(apc)  # IntervalValues
            self.productionCosts[my_energy_type] = [x for x in self.productionCosts[my_energy_type] if x.timeInterval in ti]

            # Sum the total production cost
            #self.totalProductionCost = sum([self.productionCosts.value])
            self.totalProductionCost = self.totalProductionCost + sum([x.value for x in self.productionCosts[my_energy_type]])  # total production cost [$]

    def update_vertices(self, mkt):
        # Create vertices to represent the asset's flexibility
        #
        # For the base local asset model, a single, inelastic power is needed.
        # There is no flexibility. The constant power may be represented by a
        # single (price, power) point (See struct Vertex).

        # Gather active time intervals
        ti = mkt.timeIntervals  # active TimeIntervals

        # gather information on energy types
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types =1

        # Index through active time intervals ti
        for i in range(len(ti)):  # for i = 1:len(ti):
            # index through the types of energy
            for i_energy_type in range(n_energy_types):
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal
                # check to see if this local asset has that energy type
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                # if this local asset doesn't have that energy type, move on to the next one
                else:
                    continue

                # Find the scheduled power for the indexed time interval
                # Extract the scheduled power value
                sp = find_obj_by_ti(self.scheduledPowers[my_energy_type], ti[i])
                sp = sp.value  # avg. kW]

                # Create the vertex that can represent this (lack of) flexibility
                #value = Vertex(inf, 0.0, sp, true)  # See struct Vertex
                value = Vertex(float("inf"), 0.0, sp, True)

                # Check to see if the active vertex already exists for this indexed
                # time interval.
                #iv = findobj(self.activeVertices, 'timeInterval', ti(i))
                iv = find_obj_by_ti(self.activeVertices[my_energy_type], ti[i])

                # If the active vertex does not exist, a new interval value must be
                # created and stored.

                if iv is None:

                    # Create the interval value and place the active vertex in it
                    #iv = IntervalValue(obj, ti(i), mkt, 'ActiveVertex', value)
                    iv = IntervalValue(self, ti[i], mkt, MeasurementType.ActiveVertex, value)

                    # Append the interval value to the list of active vertices
                    self.activeVertices[my_energy_type].append(iv)
                else:

                    # Otherwise, simply reassign the active vertex value to the
                    # existing listed interval value. (NOTE that this base local
                    # asset model unnecessarily reassigns constant values, but the
                    # reassignment is allowed because it teaches how a more dynamic
                    # assignment may be maintained.
                    iv.value = value
