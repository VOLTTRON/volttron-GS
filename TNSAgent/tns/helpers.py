
import math
from datetime import datetime, timedelta

from vertex import Vertex
#from time_interval import TimeInterval
from interval_value import IntervalValue
from measurement_type import MeasurementType
from numpy import argsort


def format_date(dt):
    return dt.strftime('%Y%m%d')


def format_ts(dt):
    return dt.strftime('%Y%m%dT%H%M%S')


def get_duration_in_hour(dur):
    if isinstance(dur, timedelta):
        dur = dur.seconds // 3600
    return dur

def find_objs_by_ti(items, ti):
    found_items = [x for x in items if x.timeInterval == ti]
    return found_items


def find_obj_by_ti(items, ti):
    found_items = [x for x in items if x.timeInterval == ti]
    return found_items[0] if len(found_items) > 0 else None

def find_objs_by_st(items, value):
    found_items = [x for x in items if x.startTime == value]
    return found_items


def find_obj_by_st(items, value):
    found_items = [x for x in items if x.startTime == value]
    return found_items[0] if len(found_items) > 0 else None


def is_heavyloadhour(datetime_value):
    """True if time is within a HLH hour
    """
    is_hlh = False
    if not isinstance(datetime_value, datetime):
        raise 'Input value has to be an instance of datetime'

    #These holidays are always LLH. If New Year's Day, Independence Day, or
    #Labor Day fall on a Sunday, the following Monday is LLH. These dates
    holidays = [
        "2018-01-01",
        "2018-05-28",
        "2018-07-04",
        "2018-09-03",
        "2018-11-22",
        "2018-12-25"
    ]
    #should be maintained far into the future.

    #The basic definition of HLH is based on hour and weekday memberships.
    h = datetime_value.hour
    d = datetime_value.weekday()
    d_str = format_date(datetime_value)
    is_holiday = d_str in holidays
    is_in_hlh_hours = 6 <= h <= 21
    is_sunday = d == 6  # Sunday

    if is_in_hlh_hours and not is_sunday and not is_holiday:
        is_hlh = True

    return is_hlh


def order_vertices(uv):
    return sorted(uv, key=lambda x: (x.marginalPrice, x.power))


def prod_cost_from_vertices(obj, ti, pwr, energy_type = MeasurementType.PowerReal, market=[]):
    #  PROD_COST_FROM_VERTICES - Infer production cost for a power from the
    #  vertices that define an object's supply curve
    #
    #  If the neighbor is not a "friend" (an insider that is owned by the same
    #  business entity), it is probably represented by a production cost that
    #  includes both production costs and profits. If, however, the neighbor is
    #  a friend, it may offer a blended price that eliminates some, if not all,
    #  local profit.
    #
    #  PRESUMPTIONS:
    #  - This method applies to NeighborModel and LocalAssetModel objects.
    #  Method properties must be named identically in these object classes.
    #  - A supply curve exists for the object, as defined by a set of active
    #  vertices. The vertices are up-to-date. See struct Vertex().
    #  - Vertex property "cost" defines the total, accurate production cost
    #  for the object at the vertex's power. The marginal price and slope of
    #  segment between successive vertices must be used to infer production
    #  cost between vertices.
    #  - Production costs must be accurate and meaningful. An ideal is that
    #  the production costs estimate or displace the dynamic delivered cost
    #  of electricity. If production costs are well-tracked, production
    #  costs should be equivalent to electricity costs over time.
    #
    #  INPUTS:
    #  obj - the neighbor model 3object
    #  ti - the active time interval
    #  pwr - the average power at which the production cost is to be
    # calculated. This will be the scheduled power during scheduling.
    # It may be power at other active vertices for the calculation of
    # flexibility.
    #
    #  OUTPUTS:
    #  cost - production cost in the time interval ti [$]
    #
    #  VERSIONING
    #  0.15 2019-08 Panossian
    #   - debugged function to output the cost as an intervalValue instead of a float so that
    #       values have associated time stamps
    #  0.1 2018-01 Hammerstrom
    #  - Generalized function from a method of NeighborModel. Should be usable
    #  by either neighbor or asset models, I think.

    #  We presume only generation and importation of electricity (i.e., p>0)
    #  contribute to production costs
    # power consumption may have a production cost if the asset is flexible
    # if pwr < 0.0:
    #     cost = 0.0
    #     return cost

    #  Find the active vertices for the object in the given time interval
    #v = findobj(obj.activeVertices, 'timeInterval', ti)  # IntervalValues
    if isinstance(obj.activeVertices[0], list):
        if energy_type in obj.measurementType:
            i_energy_type = obj.measurementType.index(energy_type)
            v = [x for x in obj.activeVertices[i_energy_type] if x.timeInterval == ti]
        else:
            cost = IntervalValue(obj, ti, market, MeasurementType.ProductionCost, 0.0)
            return cost
    else:
        v = [x for x in obj.activeVertices if x.timeInterval == ti]

    #  number of active vertices len in the indexed time interval
    v_len = len(v)

    if v_len == 0:  # No vertices were found in the given time interval
        print(' '.join(['No active vertices are found for',
                        obj.name, '. Returning without finding',
                        'production cost.']))
        return

    elif v_len == 1:  # One vertex was found in the given time interval

        # Extract the vertex from the interval value
        v = v[0].value  # a production vertex

        # There is no flexibility. Assign the production value from the
        # constant production as indicated by the lone vertex.
        cost = IntervalValue(obj, ti, market, MeasurementType.ProductionCost, v.cost)  # production cost [$]
        return cost

    else:  # There is more than one vertex

        # Extract the production vertices from the interval values
        v = [x.value for x in v]  # vertices

        # Sort the vertices in order of increasing marginal price and
        # power
        v = sort_vertices(v, 'marginalPrice')  # sorted production vertices
        #v.sort()

# Special case when neighbor is at its minimum power.
        if pwr <= v[0].power:

            # Production cost is known from the vertex cost.
            cost = v[0].cost  # production cost [$]
            cost = IntervalValue(obj, ti, market, MeasurementType.ProductionCost, cost)
            return cost
        # Special case when neighbor is at its maximum power.
        elif pwr >= v[-1].power:
            #
            # Production cost may be inferred from the blended price at the
            # maximum production vertex.
            cost = v[-1].cost  # production cost [$]
            return IntervalValue(obj, ti, market, MeasurementType.ProductionCost, cost)
            # Remaining case is that neighbor power is between defined
            # production indices.

        else:

            # Index through the production vertices v in this time interval
            for k in range(v_len-1):  # for k = 1:(len - 1):
                if v[k].power <= pwr < v[k+1].power:

                    # The power is found to lie between two of the vertices.

                    # Constant term (an integration constant from lower
                    # vertex
                    a0 = v[k].cost  # [$]

                    # First-order term for the segment is based on the
                    # marginal price of the lower vertex and the power
                    # exceeding that of the lower vertex
                    # NOTE: Matlab function hours() toggles duration back to
                    # a numeric value, which is correct here.
                    #dur = ti.duration
                    #if isduration(dur):
                    #  dur = hours(dur)  # toggle duration to numeric
                    dur = get_duration_in_hour(ti.duration)
                    a1 = v[k].marginalPrice  # [$/kWh]
                    a1 = a1 * (pwr - v[k].power)  # [$/h]
                    a1 = a1 * dur  # [$]

                    # Second-order term is derived from the slope of the
                    # current segment of the supply curve and the square of
                    # the power in excess of the lower vertex
                    if v[k+1].power == v[k].power:

                        # An exception is needed for infinite slope to avoid
                        # division by zero
                        a2 = 0.0  # [$]

                    else:
                        # NOTE: Matlab function hours() toggles a duration
                        # back to a numeric, which is correct here.
                        #dur = ti.duration
                        #if isduration(dur)
                        #  dur = hours(dur)  # toggle duration to numeric

                        a2 = v[k+1].marginalPrice - v[k].marginalPrice
                        #  [$/kWh]
                        a2 = a2 / (v[k+1].power - v[k].power)  # [$/kWh/kW]
                        a2 = a2 * (pwr - v[k].power) ** 2  # [$/h]
                        a2 = a2 * dur  # [$]

                    # Finally, calculate the production cost for the time
                    # interval by summing the terms
                    cost = a0 + a1 + a2  # production cost [$]

                    # Return. Production cost has been calculated.
                    return IntervalValue(obj, ti, market, MeasurementType.ProductionCost, cost)


def prod_cost_from_formula(obj, ti):
    # PROD_COST_FROM_FORMULA() -  Calculate production cost from a quadratic
    # production-cost formula
    #
    # This formulation allows for a quadratic cost function. Objects have cost
    # parameters that allow the calculation of production cost from the power
    # and these cost coefficients
    # production cost = a0 + a1*p + 0.5*a2*p^2
    #
    # INPUTS:
    # obj - Either a NeighborModel or LocalAssetModel object
    # ti - time interval (See TimeInterval class)
    #
    # OUTPUTS:
    # cost - production cost in absolute dollars for time interval ti [$]

    # Get the object's quadratic cost coefficients
    a = obj.costParameters

    # Find the scheduled power sp in time interval ti
    #sp = findobj(obj.scheduledPowers, 'timeInterval', ti)  # An IntervalValue
    sp = find_obj_by_ti(obj.scheduledPowers, ti)

    # Extract the scheduled-power value
    sp = sp.value  # [avg.kW]

    # Calculate the production cost from the quadratic cost formula
    # Constant term
    cost = a[0]  # [$/h]

    # Add the first-order term
    cost = cost + a[1] * sp  # [$/h]

    # Add the second order term
    #cost = cost + 0.5 * a[2] * sp ^ 2  # [$/h]
    cost = cost + 0.5 * a[2] * sp**2  # [$/h]

    # Convert to absolute dollars
    # NOTE: Matlab function hours() toggles from duration to numeric, which
    # is correct here.
    #dur = ti.duration
    #if isduration(dur)
    #  dur = hours(dur)  # toggle from duration to numberic
    dur = get_duration_in_hour(ti.duration)

    cost = cost * dur  # interval production cost [$]

    return cost


def production(obj, price, ti, energy_type=None):
    # FUNCTION PRODUCTION()
    # Find economic power production for a marginal price and time interval
    # using an object model's demand or supply curve. This is performed as a
    # linear interpolation of a discrete set of price-ordered vertices (see
    # struct Vertex).
    #
    # obj - Asset or neighbor model for which the power production is to be
    # calculated. This model has a set of "active vertices" that define
    # its flexibility via a demand or supply curve.
    # price - marginal price [$/kWh]
    # ti - time interval (see class TimeInterval)
    # [p1] - economic power production in the given time interval   and at
    #  the given price (positive for generation) [avg.kW].
    #
    # VERSIONING
    # 0.3 2019-05 Panossian
    # - modified to allow for multiple energy types at the objects
    # 0.2 2017-11 Hammerstrom
    # - Corrected for modifications to Vertex() properties. There are now
    # two prices. This one should reference property marginalPrice.
    # 0.1 2017-11 Hammerstrom
    # - Original function draft
    # *************************************************************************

    # Find the active production vertices for this time interval (see class IntervalValue).
    #pv = findobj(obj.activeVertices, 'timeInterval', ti)  # IntervalValues
    # accomodate list of lists
    if energy_type == None:
        pv = find_objs_by_ti(obj.activeVertices, ti)
    else:
        if energy_type in obj.measurementType:
            i_energy_type = obj.measurementType.index(energy_type)
            pv = find_objs_by_ti(obj.activeVertices[i_energy_type],ti)
        else:
            pass

        # Extract the vertices (see struct Vertex) from the interval values (see IntervalValue class).
        pvv = [x.value for x in pv]  # vertices

        # Ensure that the production vertices are ordered by increasing price.
        # Vertices having same price are ordered by power.
        pvv = order_vertices(pvv)  # vertices

        # Number len of vertices in the list.
        pvv_len = len(pvv)

        if pvv_len == 0:  # No active vertices were found in the given time interval
            raise(' '.join(['No active vertices were found for', obj.name, 'in time interval', ti.name]))

        if pvv_len == 1:  # One active vertices were found in the given time interval
            # Presume that using a single production vertex is shorthand for
            # constant, inelastic production.
            p1 = pvv[0].power  # [avg.kW]
            return p1

        else:  # Multiple active vertices were found
            if price < pvv[0].marginalPrice:
                # Special case where marginal price is before first vertex.
                # The power is at its minimum.
                p1 = pvv[0].power  # [kW]
                return p1

            elif price >= pvv[-1].marginalPrice:
                # Special case where marginal price is after the last
                # vertex. The power is at its maximum.
                p1 = pvv[-1].power  # [kW]
                return p1

            else:  # The marginal price lies among the active vertices
                # Index through the active vertices pvv in the given time
                # interval ti
                for i in range(pvv_len-1):  # for i = 1:len - 1

                    if pvv[i].marginalPrice <= price < pvv[i+1].marginalPrice:

                        # The marginal price falls between two vertices that
                        # are sloping upward to the right. Interpolate
                        # between the vertices to find the power production.
                        p1 = pvv[i].power \
                            + (price - pvv[i].marginalPrice) \
                            * (pvv[i+1].power - pvv[i].power) \
                            / (pvv[i+1].marginalPrice - pvv[i].marginalPrice)  # [avg.kW]
                        return p1

                    #elif price == pvv[i].marginalPrice and pvv[i].marginalPrice == pvv[i+1].marginalPrice:
                    elif price == pvv[i].marginalPrice == pvv[i+1].marginalPrice:

                        # The marginal price is the same as for two vertices
                        # that lie vertically at the same marginal price.
                        # Assign the power of the vertex having greater
                        # power.
                        p1 = pvv[i+1].power  # [kW]
                        return p1

                    elif price == pvv[i].marginalPrice:

                        # The marginal price is the same as the indexed
                        # active vertex. Use its power value.
                        p1 = pvv[i].power  # [kW]
                        return p1



def are_different1(s, r, threshold):
    # ARE_DIFFERENT1() - Returns true is two sets of TransactiveRecord objects,
    # representing sent and received messages in a time interval, are
    # significantly different.
    #
    # INPUTS:
    # s - sent TransactiveRecord object(s) (see struct TransactiveRecord)
    # r - received TransactiveRecord object(s)
    # threshold - relative error used as convergence criterion. Two messages
    #   differ significantly if the relative distance between the
    #   scheduled points (i.e., Record 0) differ by more than this
    #   threshold.
    #
    # OUTPUS:
    # tf - Boolean: true if relative distance between scheduled (i.e., Record
    #  0) (price,quantity) pairs in the two messages exceeds the
    #  threshold.

    # Pick out the scheduled sent and received records (i.e., the one where
    # record = 0).
    s0 = s([s.record] == 0)  # a TransactiveRecord
    r0 = r([r.record] == 0)  # a TransactiveRecord

    # Calculate the difference dmp in scheduled marginal prices.
    dmp = abs(s0.marginalPrice - r0.marginalPrice)  # [$/kWh]

    # Calculate the average mp_avg of the two scheduled marginal prices.
    mp_avg = 0.5 * abs(s0.marginalPrice + r0.marginalPrice)  # [$/kWh]

    # Calculate the difference dq betweent the scheduled powers.
    dq = abs(-s0.power - r0.power)  # [avg. kW]

    # Calculate the average q_avg of the two scheduled average powers.
    q_avg = 0.5 * abs(r0.power + -s0.power)  # [avg. kW]

    # Calculate the relative Euclidian distance d (a relative error
    # criterion) between the two scheduled (price,quantity) points.
    if len(s) == 1 or len(r) == 1:
        d = dq / q_avg  # dimensionless
    else:
        d = math.sqrt((dq / q_avg) ^ 2 + (dmp / mp_avg) ^ 2)  # dimensionless

    if d > threshold:

        # The distance, or relative error, between the two scheduled points
        # exceeds the threshold criterion. Return true to indicate that the
        # two messages are significantly different.
        tf = True

    else:

        # The distance, or relative error, between the two scheduled points
        # is less than the threshold criterion. Return false, meaning that
        # the two messages are not significantly different.
        tf = False

    return tf


def are_different2(m, s, threshold):
    # ARE_DIFFERENT2() - Assess whether two TransactiveRecord messages,
    # representing the calculated and sent messages in an active time interval
    # are significantly different from one another. If the signals are
    # different, this indicates that local conditions have changed, and a
    # revised, updated transactive message shoudl be sent to the Neighbor.
    #
    # INPUTS:
    # m - TransactiveRecord message representing the mySignal, the last
    #   message calculated for this transactiveNeighbor.
    # s - TransactiveRecord messge representing the sentSignal, the last
    #   message that was sent to this transactive Neighbor.
    # threshold - a dimensionless, relative error that is used as a convergence
    # criterion.
    #
    # OUTPUTS:
    # tf - Boolean: true if the sent and recently calculated transactive
    #    messages are significantly different.

    if len(s) == 1 or len(m) == 1:
        # Either the sent or calculated message is a constant, (i.e., one
        # Vertex) meaning its marginal price is probaly NOT meaningful. Use
        # only the power in this case to determine whether they differ.
        # Pick out the scheduled values (i.e., Record 0) from mySignal and
        # sentSignal records.
        m0 = m([m.record] == 0)
        s0 = s([s.record] == 0)

        # Calculate the difference dq between the scheduled powers in the two
        # sets of records.
        dq = abs(m0.power - s0.power)  # [avg.kW]

        # Calculate the average scheduled power avg_q of the two sets of
        # records.
        avg_q = 0.5 * abs(m0.power + s0.power)  # [avg.kW]

        # Calculate relative distance d between the two scheduled powers.
        # Avoid the unlikely condition that the average power is zero.
        if avg_q != 0:
            d = dq / avg_q
        else:
            d = 0

        if d > threshold:
            # The difference is greater than the criterion. Return true,
            # meaning that the difference is significant.
            tf = True
        else:
            # The difference is less than the criterion. Return false,
            # meaning the difference is not significant.
            tf = False

    else:
        # There are multiple records, meaning that the Neighbor is
        # price-responsive.

        # Pick out the records that are NOT scheduled points, i.e., are not
        # Record 0. Local convergence of the coordination sub-problem does
        # not require so much that the exact point has been determined as
        # that the flexibility is accurately conveyed to the Neighbor.
        m0 = m([m.record] != 0)
        s0 = s([s.record] != 0)

        # Index through the sent and calculated flexibility records. See if
        # any record cannot be matched with a corresponding member of
        # mySignal m0.
        for i in range(len(s0)):  # for i = 1:length(s0)

            tf = True

            for j in range(len(m0)):  # for j = 1:length(m0)

                # Calculate difference dmp between marginal prices .
                dmp = abs(s0(i).marginalPrice - m0(j).marginalPrice)  # [$/kWh]

                # Calculate average avg_mp of marginal price pair.
                avg_mp = 0.5 * (s0(i).marginalPrice + m0(j).marginalPrice)  # [$/kWh]

                # Calculate difference dq between power values in the two sets of
                # records.
                dq = abs(s0(i).power - m0(j).power)  # [avg.kW]

                # Calculate average avg_q of power pairs in the two sets of
                # records.
                avg_q = abs(s0(i).power + m0(j).power)  # [avg.kW]

                # If no pairing between the flexibility records of the two sets
                # of records can be found within the relative error criterion,
                # things must have changed locally since the transactive message
                # was last sent.
                if math.sqrt((dmp / avg_mp) ^ 2 + (dq / avg_q) ^ 2) <= threshold:

                    #   No pairing was found within the relative error criterion
                    #   distance. Things must have changed locally since the
                    #   transactive message was last sent to the transactive
                    #   Neighbor. Set the flag true.
                    tf = False
                    continue

            if tf:
                return tf

def sort_vertices(v, property):
    v2 = v
    v = [getattr(x,property) for x in v]
    indv = argsort(v)
    v_sorted = []
    for i in range(len(indv)):
        indv_i = indv[i]
        v_sorted.append(v2[indv_i])
    #v_sorted = [v2[indv[0]], v2[indv[1]]]
    return v_sorted