from datetime import datetime

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
from const import *

import logging
#utils.setup_logging()
_log = logging.getLogger(__name__)


class BulkSupplier_dc(NeighborModel):
    # BulkSupplier NeighborModel subclass - Represents non-transactive
    # neighbor, including demand charges
    #
    # Created to represent large, non-transactive electricity supplier BPA in
    # its relationship to a municipality. 
    # - Introduces new properties to keep track of peak demand.
    # - Calls on a new function to determine hour type (HLH or LLH).
    # - Mines tables to determine monthly electricity and demand rates in HLH
    # and LLH hour types.

    def __init__(self):
        super(BulkSupplier_dc, self).__init__()
        self.transactive = False
        
    def update_dc_threshold(self, mkt):
        # UPDATE_DC_THRESHOLD() - keep track of the month's demand-charge threshold
        # obj - BulkSupplier_dc object, which is a NeighborModel
        # mkt - Market object
        #
        # Pseudocode:
        # 1. This method should be called prior to using the demand threshold. In
        #  reality, the threshold will change only during peak periods.
        # 2a. (preferred) Read a meter (see MeterPoint) that keeps track of an
        # averaged power. For example, a determinant may be based on the
        # average demand in a half hour period, so the MeterPoint would ideally
        # track that average.
        # 2b. (if metering unavailable) Update the demand threshold based on the
        # average power in the current time interval.
        
        # Find the MeterPoint object that is configured to measure average demand
        # for this NeighborModel. The determination is based on the meter's
        # MeasurementType.
        #mtr = findobj(self.meterPoints, 'MeasturementType', MeasurementType('average_demand_kW'))  # a MeterPoint object
        mtr = [x for x in self.meterPoints if x.measurementType == MeasurementType.AverageDemandkW]

        if len(mtr) == 0:  #if isempty(mtr)
        
            # No appropriate MeterPoint object was found. The demand threshold
            # must be inferred.
        
            # Gather the active time intervals ti and find the current (soonest) one.
            #ti = [mkt.timeIntervals]
            #[~, ind] = sort([ti.startTime])
            #ti = ti(ind)  # ordered time intervals from soonest to latest
            ti = mkt.timeIntervals
            ti.sort(key=lambda x: x.startTime)
        
            # Find current demand d that corresponds to the nearest time interval.
            #d = findobj(self.scheduledPowers, 'timeInterval', ti(1))  # [avg.kW]
            d = find_obj_by_ti(self.scheduledPowers, ti[0])
        
            # Update the inferred demand.
            self.demandThreshold = max([0, self.demandThreshold, d.value])  # [avg.kW]
        
        else:
        
            # An appropriate MeterPoint object was found. The demand threshold
            # may be updated from the MeterPoint object.
        
            # Update the demand threshold.
            self.demandThreshold = max([0, self.demandThreshold, mtr[0].currentMeasurement])  # [avg.kW]

        if len(mtr) > 1:
        
            # More than one appropriate MeterPoint object was found. This is a
            # problem. Warn, but continue.
            _log.warning('The BulkSupplier_dc object is associated with too many average-damand meters')

        
        # The demand threshold should be reset in a new month. First find the
        # current month number mon.
        dt = datetime.now()
        mon = dt.month
        
        if mon != self.demandMonth:
        
            # This must be the start of a new month. The demand threshold must be
            # reset. For now, "resetting" means using a fraction (e.g., 80#) of
            # the final demand threshold in the prior month.
            self.demandThreshold = 0.8 * self.demandThreshold
            self.demandMonth = mon
        
        
    def update_vertices(self, mkt):
        # Creates active vertices for a non-transactive neighbor, including demand
        # charges.
        #
        # INPUTS:
        # obj - Bulk supplier non-transactive neighbor model object
        # mkt - Market object
        #
        # OUTPUTS:
        # - Updates self.activeVertices for active time intervals.
        
        # Gather active time intervals
        time_intervals = mkt.timeIntervals  # TimeInterval objects
        
        # Get the maximum power maxp for this neighbor.
        maximum_power = self.object.maximumPower  # [avg.kW]
        
        # The maximum power property is meaningful for both imported (p>0) and
        # exported (p<0) electricity, but this formulation is intended for
        # importation (power>0) from an electricity supplier. Warn the user and
        # return if the maximum power is negative.
        if maximum_power < 0:
            _log.warning('Maximum power must be positive in BulkSupplier_dc.m')
            _log.warning('Returning without creating active vertices for ' + self.name)
            return

        # Get the minimum power for this neighbor.
        minimum_power = self.object.minimumPower  # [avg.kW]
        
        # Only importation is supported from this non-transactive neighbor.
        if minimum_power < 0:
            _log.warning('Minimum power must be positive in "BulkSupplier_dc.m')
            _log.warning('Returning without creating active vertices for ' + self.name)
            return

        # Cost coefficient a0. This is unavailable from a supply curve, so it
        # must be determined directly from the first, constant cost parameter.
        # It does NOT affect marginal pricing.
        a0 = self.costParameters[0]  # [$/h]
        
        # Full-power loss at is defined by the loss factor property and the
        # maximum power.
        full_power_loss = maximum_power * self.object.lossFactor  # [avg.kW] 
        
        # Minimum-power loss at Vertex 1 is a fraction of the full-power loss.
        # (Power losses are modeled proportional to the square of power
        # transfer.)
        minimum_power_loss = (minimum_power / maximum_power) ** 2 * full_power_loss  # [avg.kW]

        # Index through active time intervals
        for i in range(len(time_intervals)):  #for i = 1:length(time_intervals)
        
            # Find and delete active vertices in the indexed time interval.
            # These vertices shall be recreated.
            #indices = ~ismember([self.activeVertices.timeInterval], time_intervals[i])  # array of logicals
            #self.activeVertices = self.activeVertices(indices)
            self.activeVertices = [x for x in self.activeVertices if x != time_intervals[i]]
            
            # Find the month number for the indexed time interval start time.
            # The month is needed for rate lookup tables.
            month_number = time_intervals[i].startTime.month  #month(time_intervals[i].startTime)
            
            if is_heavyloadhour(time_intervals[i].startTime):
            
                # The indexed time interval is an HLH hour. The electricity rate
                # is a little higher during HLH hours, and demand-charges may
                # apply.
                # Look up the BPA energy rate for month_number. The second
                # parameter is HLH = 1 (i.e., column 1 of the table).
                energy_rate = bpa_energy_rate[month_number-1][0]  # HLH energy rate [$/kWh]
            
                # Four active vertices are initialized:
                # #1 at minimum power
                # #2 at the demand-charge power threshold
                # #3 at the new demand rate and power threshold
                # #4 at maximum power and demand rate
                vertices = [Vertex(0, 0, 0), Vertex(0, 0, 0), Vertex(0, 0, 0), Vertex(0, 0, 0)]
            
                ## Evaluate the first of the four vertices
                # Segment 1: First-order parameter a1. 
                # This could be stated directly from cost parameters, but this
                # model allows for dynamic rates, accounts for losses, and models
                # demand-charges, which would require defining multiple
                # cost-parameter models. The first-order parameter is the
                # electricity rate. In this model, the rate is meaningful at a
                # neighbor node location at zero power transfer.
                a1 = energy_rate  # [$/kWh]
            
                # Vertex 1: Full available power transfer at Vertex 1 is thus the
                # physical transfer limit, minus losses.
                vertices[0].power = (minimum_power - minimum_power_loss)
            
                # Vertex 1: Marginal price of Vertex 1 is augmented by the value
                # of energy from the neighbor that is lost. (This model assigns
                # the cost of losses to the recipient (importer) of electricity.)
                vertices[0].marginalPrice = a1 * (1 + self.object.lossFactor * minimum_power / maximum_power)  # [$/kWh]
            
                ## Evalauate the second of four vertices            
                # Vertex 2: Available power at Vertex 2 is determined by the
                # current peak demand charge threshold pdt and possibly scheduled
                # powers prior to the indexed time interval. The demand threshold
                # in the indexed time interval is at least equal to the
                # parameter. NOTE this process will work only if the demand
                # threshold is is updated based on actual, accurate measurements.
                peak_demand_threshold = self.demandThreshold  # [kW]
                
                # Also consider, however, scheduled powers prior to the indexed
                # interval that might have already set a new demand threshold.
                # For simplicity, presume that new demand thresholds would occur
                # only during HLH hour types. More complex code will be needed
                # if only HLH hours must be considered. NOTE this process will
                # work only if the load forcasts are meaningful and accurate.
                
                # Gather scheduled powers sp
                scheduled_powers = self.scheduledPowers

                if len(scheduled_powers) == 0:  #if ~isempty(scheduled_powers)
                
                    # Powers have been scheduled, order the scheduled powers by
                    # their start time 
                    #interval_start_times = [self.scheduledPowers.timeInterval]  # IntervalValue objects
                    #interval_start_times = [interval_start_times.startTime]  # datetimes
                    #[~, index] = sort(interval_start_times)  # logical array
                    #ordered_scheduled_powers = self.scheduledPowers(index)  # IntervalValue objects ordered by start times
                    ordered_scheduled_powers = sorted(self.scheduledPowers, key=lambda x: x.timeInterval.startTime)
                    ordered_scheduled_powers = ordered_scheduled_powers[:i+1]

                    # The peak demand determinant is the greater of the monthly
                    # peak threshold or the prior scheduled powers.
                    ordered_scheduled_powers = [x.value for x in ordered_scheduled_powers]
                    ordered_scheduled_powers.append(peak_demand_threshold)
                    peak_demand_threshold = max(ordered_scheduled_powers)  # kW
            
                # Vertex 2: The power at which demand charges will begin accruing
                # and therefore marks the start of Vertex 2. It is not affected
                # by losses because it is based on local metering.
                vertices[1].power = peak_demand_threshold  # [avg.kW]
                
                # Vertex 2: Marginal price of Vertex 2 is augmented by the value
                # of energy from the neighbor that is lost.
                vertices[1].marginalPrice = a1 * (1 + self.object.lossFactor * vertices[1].power / maximum_power)  # [$/kWh]
                
                ## Evaluate the third of four vertices
                # Look up the demand rate dr for the month_number. The second
                # parameter is HLH = 1 (i.e., the first column of the table).
                demand_rate = bpa_demand_rate[month_number-1][0]  #bpa_demand_rate(month_number, 1)  # [$/kW (per kWh)]
                
                # Vertex 3: The power of Vertex 3 is the same as that of Vertex 2            
                #vertices[2].power = vertices[1].power  # [avg.kW]
                vertices[2].power = peak_demand_threshold  # [avg.kW]

                # Vertex 3: The marginal price at Vertex 3 is shifted strongly by
                # the demand response rate. The logic here is that cost is
                # determined by rate * (power-threshold). Therefore, the
                # effective marginal rate is augmented by the demand rate itself.
                # NOTE: Some hand-waving is always needed to compare demand and
                # energy rates. This approach assigns a meaningful production
                # cost, but it is not correct to say it describes an energy
                # price. The cost is assigned to the entire hour. Shorter time
                # intervals should not be further incremented. Evenso, a huge
                # discontinuity appears in the marginal price.
                vertices[2].marginalPrice = vertices[2].marginalPrice + demand_rate  # [$/kWh]
                
                ## Evaluate the fourth of four vertices            
                # Vertex 4: The power at Vertex 4 is the maximum power, minus
                # losses
                vertices[3].power = maximum_power - full_power_loss  # [avg.kW]
                
                # The marginal price at Vertex 4 is affected by both losses and
                # demand charges.
                
                # Marginal price at Vertex 3 from loss component
                vertices[3].marginalPrice = a1 * (1 + self.object.lossFactor)  # [$/kWh]
                
                # Augment marginal price at Vertex 4 with demand-charge impact
                vertices[3].marginalPrice = vertices[3].marginalPrice + demand_rate  # [$/kW (per hour)]
                
                ## Assign production costs for the four vertices
                # Segment 1: The second-order cost coefficient a2 on the first
                # line segment is determined from the change in marginal price
                # divided by change in power.
                a2 = (vertices[1].marginalPrice - vertices[0].marginalPrice)  # [$/kWh]
                a2 = a2 / (vertices[1].power - vertices[0].power)  # [$/kW^2h]
                
                # Vertex 1: The cost at Vertex 1 can be inferred by integrating
                # from p=0 to Vertex 1.
                vertices[0].cost = a0 + a1 * vertices[0].power + 0.5 * a2 * (vertices[0].power) ** 2  # production cost [$/h]
                
                # Vertex 2: The cost at Vertex 2 is on the same trajectory
                vertices[1].cost = a0 + a1 * vertices[1].power + 0.5 * a2 * (vertices[1].power) ** 2  # production cost [$/h]
                
                # Vertex 3: Both the power and production cost should be the same
                # at Vertex 3 as for Vertex 2.
                vertices[2].cost = vertices[1].cost  # production cost [$/h]
                
                # Vertex 4: The cost on the third line segment has a new
                # trajectory that begins with the cost at Vertex 3 (an
                # integration constant).
                vertices[3].cost = vertices[2].cost
                # partial production cost [#/h]
                
                # Segment 3: The new first-order term for the third line segment
                # is the marginal price at Vertex 3. This applies only to power
                # imports that exceed Vertex 3.
                a1 = vertices[2].marginalPrice
                # first-order coefficient [$/kWh]
                
                # Vertex 4: Add the first-order term to the Vertex-4 cost
                vertices[3].cost = vertices[3].cost + a1 * (vertices[3].power - vertices[2].power)
                # partial production cost [$/h]
                
                # Segment 3: NOTE: The second-order coeffiecient a2 on the second
                # line segment is unchanged from the first segment
                
                # Vertex 4: Add the second-order term to the Vertex-4 cost.
                vertices[3].cost = vertices[3].cost + 0.5 * a2 * (vertices[3].power - vertices[2].power) ** 2
                # production cost [$/h]
                
                # Convert the costs to raw dollars
                # NOTE: This usage of Matlab hours() toggles a duration back
                # into a numerical representation, which is correct here.
                #interval_duration = time_intervals[i].duration
                #if isduration(interval_duration)
                    # NOTE: Matlab hours() toggles back to numeric and is fine
                    # here
                #    interval_duration = hours(interval_duration)
                #end
                interval_duration = get_duration_in_hour(time_intervals[i].duration)

                vertices[0].cost = vertices[0].cost * interval_duration  # [$]
                vertices[1].cost = vertices[1].cost * interval_duration  # [$]
                vertices[2].cost = vertices[2].cost * interval_duration  # [$]
                vertices[3].cost = vertices[3].cost * interval_duration  # [$]
                
                # Create interval values for the active vertices
                interval_values = [
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[0]),
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[1]),
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[2]),
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[3])]
                
                # Append the active vertices to the list of active vertices
                # in the indexed time interval
                #self.activeVertices = [self.activeVertices, interval_values]
                self.activeVertices.extend(interval_values)
            
            else:  # indexed time interval is a LLH hour
            
                ## LLH hours          
                # The indexed time interval is a LLH hour. The electricity rate
                # is a little lower, and demand charges are not applicable.
                # 
                # Look up the BPA energy rate for month m. The second parameter
                # is LLH = 2 (i.e., column 2 of the table).
                energy_rate = bpa_energy_rate[month_number-1][1]  #bpa_energy_rate(month_number, 2)
                
                # Two active vertices are created
                # #1 at minimum power
                # #2 at maximum power
                vertices = [Vertex(0, 0, 0), Vertex(0, 0, 0)]
                
                ## Evaluate the first of two vertices            
                # First-order parameter a1.
                a1 = energy_rate  # [$/kWh]
                
                # Vertex 1: Full available power transfer at Vertex 1 is thus the
                # physical transfer limit, minus losses.
                vertices[0].power = (minimum_power - minimum_power_loss)
                # [avg.kW]
                
                # Vertex 1: Marginal price of Vertex 1 is augmented by the value
                # of energy from the neighbor that is lost. (This model assigns
                # the cost of losses to the recipient (importer) of electricity.)
                vertices[0].marginalPrice = a1 * (1 + self.object.lossFactor * minimum_power / maximum_power)  # [$/kWh]
                
                ## Evaluate the second of two vertices                          
                # Vertex 2: The power at Vertex 2 is the maximum power, minus
                # losses
                vertices[1].power = maximum_power - full_power_loss  # [avg.kW]
                
                # Vertex 2: The marginal price at Vertex 2 is affected only by
                # losses. Demand charges do not apply during LLH hours.
                # 
                # Vertex 2: Marginal price at Vertex 2 from loss component
                vertices[1].marginalPrice = a1 * (1 + self.object.lossFactor)  # [$/kWh]
                
                ## Assign production costs for the two vertices
                # The second-order cost coefficient a2 on the lone line segment
                # is determined from the change in marginal price divided by
                # change in power.
                a2 = (vertices[1].marginalPrice - vertices[0].marginalPrice)  # [$/kWh]
                a2 = a2 / (vertices[1].power - vertices[0].power)  # [$/kW^2h]
                
                # The cost at Vertex 1 can be inferred by integrating from
                # p=0 to Vertex 1.
                vertices[0].cost = a0 + a1 * vertices[0].power + 0.5 * a2 * (vertices[0].power) ** 2  # production cost [$/h]
                
                # The cost at Vertex 2 is on the same trajectory
                vertices[1].cost = a0 + a1 * vertices[1].power + 0.5 * a2 * (vertices[1].power) ** 2  # production cost [$/h]
                
                # Convert the costs to raw dollars
                #interval_duration = time_intervals[i].duration
                #if isduration(interval_duration)
                    # Matlab function hours() toggles a duration back to numeric.
                #    interval_duration = hours(interval_duration)
                #end

                interval_duration = get_duration_in_hour(time_intervals[i].duration)

                vertices[0].cost = vertices[0].cost * interval_duration  # [$]
                vertices[1].cost = vertices[1].cost * interval_duration  # [$]
                
                # Create interval values for the active vertices
                interval_values = [
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[0]),
                    IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, vertices[1])
                ]
                
                # Append the active vertices to the list of active vertices
                # in the indexed time interval
                #self.activeVertices = [self.activeVertices, interval_values]
                self.activeVertices.extend(interval_values)
