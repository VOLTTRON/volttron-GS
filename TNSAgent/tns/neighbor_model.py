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
from local_asset import LocalAsset
from local_asset_model import LocalAssetModel
from myTransactiveNode import myTransactiveNode


class NeighborModel(Model, object):
    # NeighborModel Base Class
    # The NeighborModel manages the interface with a Neighbor object and
    # represents it for the computational agent. There is a one-to-one
    # correspondence between a Neighbor object and its NeighborModel object.
    # Members of the transactive network must be indicated by setting the
    # "transactive" property true.
    def __init__(self, measurementType = [MeasurementType.PowerReal]):
        super(NeighborModel, self).__init__()
        self.converged = False
        self.convergenceFlags = []  # IntervalValue.empty  # values are Boolean
        self.convergenceThreshold = 0.01  # [0.01 = 1#]
        self.defaultVertices = [[Vertex(float("inf"), 0.0, 1)] for mt in measurementType]#[[IntervalValue(self, ti, mkt, MeasurementType.ActiveVertex, Vertex(float("inf"), 0.0, 1))] for mt in measurementType]#[[] for mt in measurementType]
        self.demandMonth = datetime.today().month  # used to re-set demand charges
        self.demandRate = [10 for mt in measurementType]  # [$ / kW (/h)]
        self.demandThreshold = [1e9 for mt in measurementType]  # power that causes demand charges [kW]
        self.effectiveImpedance = [0.0 for mt in measurementType] # Ohms for future use
        self.friend = False  # friendly Neighbors might get preferred rates
        self.mySignal = [[] for mt in measurementType]  # TransactiveRecord.empty  # current records ready to send
        self.receivedSignal = []  # TransactiveRecord.empty  # last records received
        # NOTE: Realized late that sentSignal is needed as part of the
        # event-driven timing of the system. This allows a comparison
        # between a recent calculation (mySignal) and the last calculation
        # that was revealed to the Neighbor (sentSignal).
        self.sentSignal = []  # TransactiveRecord.empty  # last records sent
        self.transactive = False
        self.measurementType = measurementType
        self.activeVertices = [[] for mt in measurementType] 
        self.scheduledPowers = [[] for mt in measurementType] 
        self.reserveMargins = [[] for mt in measurementType] 
        self.productionCosts = [[] for mt in measurementType] 
        self.dualCosts = [[] for mt in measurementType] 

    def calculate_reserve_margin(self, mkt):
        # CALCULATE_RESERVE_MARGIN() - Estimate the spinning reserve margin
        # in each active time interval
        #
        # RESERVE MARGIN is defined here as additional generation or reduced
        # consumption above the currently scheduled power. The intention is for
        # this to represent "spinning-reserve" power that can be available on short
        # notice. 
        #
        # For now, this quantity will be tracked. In the future, treatment of
        # resource commitment may allow meaningful control of reserve margin and
        # the resiliency that it supports.
        #
        # PRESUMPTIONS:
        # - time intervals are up-to-date
        # - scheduled power is up-to-date
        # - the active vertices are up-to-date and correct. One of the vertices
        # represents the maximum power that is available on short notice (i.e.,
        # "spinning reserve") from this neighbor.
        #
        # INPUTS:
        # obj - Neighbor model object
        # mkt - Market object
        #
        # OUTPUTS:
        # - updated self.reserveMargins
        
        # Gather active time intervals ti
        time_intervals = mkt.timeIntervals

        # gather energy types
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1
        
        # Index through active time intervals ti
        for i in range(len(time_intervals)):  # for i = 1:len(time_intervals)
            # Find the maximum available power from among the active vertices in
            # the indexed time interval, one of which must represent maximum
            # power
            #maximum_power = findobj(self.activeVertices, 'timeInterval', time_intervals[i])  # IntervalValue objects
            for i_energy_type in range(n_energy_types):
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal
                # check to see if this neighbor transacts that energy type
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                # if this neighbor does not have this energy type, move on to the next one
                else: 
                    continue
                maximum_power = find_objs_by_ti(self.activeVertices[my_energy_type], time_intervals[i])
                if len(maximum_power) == 0:
                    # No active vertex was found. The hard constraint must be used.
                    maximum_power = self.object.maximumPower  # hard constraint [avg.kW]

                else:
                    # A vertex was found. Extract its power value.
                    maximum_power = [x.value for x in maximum_power]  #[maximum_power.value]  # Vertice objects
                    maximum_power = [x.power for x in maximum_power]  # real powers [avg.kW]
                    maximum_power = max(maximum_power)  # maximum power [avg.kW]

                    # Check that the operational maximum from vertices does not
                    # exceed the hard physical constraint. Use the smaller of the two.
                    maximum_power = min(maximum_power, self.object.maximumPower)

                # Find the scheduled power for this asset in the indexed time interval
                #scheduled_power = findobj(self.scheduledPowers, 'timeInterval', time_intervals[i])  # an IntervalValue
                #scheduled_power = scheduled_power.value  # scheduled power[avg.kW]
                scheduled_power = find_obj_by_ti(self.scheduledPowers[my_energy_type], time_intervals[i])
                scheduled_power = scheduled_power.value  # scheduled power [avg.kW]

                # The available reserve margin is calculated as the difference
                # between the maximum and scheduled powers. Make sure the value is
                # not less than zero.
                value = max(0, maximum_power - scheduled_power)  # reserve margin [avg.kW]

                # Check whether a reserve margin exists in the indexed time interval.
                #interval_value = findobj(self.reserveMargins, 'timeInterval', time_intervals[i])  # an IntervalValue
                interval_value = find_obj_by_ti(self.reserveMargins[my_energy_type], time_intervals[i])
                if interval_value is None:

                    # No reserve margin was found for the indexed time interval.
                    # Create a reserve margin interval for the calculated value
                    #interval_value = IntervalValue(self, time_intervals[i], mkt, 'ReserveMargin', value)  # an IntervalValue
                    interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ReserveMargin, value)

                    # Append the reserve margin interval value to the list of reserve margins.
                    self.reserveMargins[my_energy_type].append(interval_value)  # IntervalValue objects

                else:

                    # The reserve margin interval value already exists, simply
                    # reassign its value.
                    interval_value.value = value  # [avg.kW]

    def check_for_convergence(self, mkt):
        # CHECK_FOR_CONVERGENCE() - qualifies state of convergence with a
        # transactive Neighor object by active time interval and globally.
        #
        # In respect to the coordination sub-problem, a Neighbor is not converged
        # for a given time interval and a signal should be sent to the transactive
        # Neighbor if
        # - The balancing and scheduling sub-problems are converged, AND
        # - No signal has been sent, OR
        # - A signal has been received from the Neighbor, and no signal has been
        # sent since the signal was received, but scheduled power and marginal
        # price in the sent and received signals (i.e., Records 0) differ, OR
        # - A timer has elapsed since the last time a signal was sent, and the
        # sent signal differs from one that would be sent again, based on
        # current conditions.
        #
        # Inputs:
        # mdl - transactive NeighborModel model
        # mkt - Market object
        #
        # Uses property convergenceThreshold as a convergence criterion.
        #
        # Compares TransactiveRecord messages in mySignal, sentSignal, and
        # receivedSignal.
        #
        # Updates properties convergenceFlags and converged based on comparison of
        # calculated, received, and sent TransactiveRecord messages.

        # NOTE: this method should not be called unless the balancing sub-problem
        # and all the scheduling sub-problems have been calculated and have
        # converged.

        # Gather active time intervals.
        time_intervals = mkt.timeIntervals

        # Index through active time intervals to assess their convergence status.
        for i in range(len(time_intervals)):
            # Capture the current datetime in the same format as for the
            # TransactiveRecord messages.
            dt = datetime.utcnow()

            # Initialize a flag true (converged) in this time interval until
            # proven otherwise.
            flag = True

            # Find the TransactiveRecord objects sent from the transactive
            # Neighbor in this indexed active time interval. Create a logical
            # array ss, true if the received TransactiveRecord is in the indexed
            # active time interval. Then reassign ss as the targeted
            # TransactiveRecords themselves.
            #ss = ismember({self.sentSignal.timeInterval}, time_intervals(i).name)  # a logical vector
            #ss = self.sentSignal(ss)  # TransactiveRecord message in the indexed TimeStamp
            ss = [x for x in self.sentSignal if x.timeInterval == time_intervals[i].name]

            # If a sent signal message was found in the indexed time interval,
            # its timestamp ss_ts is the last time a message was sent. Otherwise,
            # set the ss_ts to the current time dt.
            if len(ss) > 0:  #if ~isempty(ss)
                #ss_ts = ss([ss.record] == 0).timeStamp  # last time message sent
                #ss_ts = datetime(ss_ts, 'Format', 'yyMMdd:HHmmss')
                ss_ts = [x.timeStamp for x in ss if x.record == 0]
                ss_ts = ss_ts[0]
            else:
                ss_ts = dt

            # Same as above, but now for received TransactiveRecord message rs in the
            # indexed active time interval.
            #rs = ismember({self.receivedSignal.timeInterval}, time_intervals(i).name)  # an array of logicals
            #rs = self.receivedSignal(rs)  # TransactiveRecords received in the indexed TimeInterval
            rs = [x for x in self.receivedSignal if x.timeInterval == time_intervals[i].name]

            # As above, if TransactiveRecords have been received, use the
            # timestamp as the last time the signal was recieved rs_ts.
            # Otherwise, use the current time instead.
            if len(rs) > 0:  # if ~isempty(ss)
                #rs_ts = rs([rs.record] == 0).timeStamp  # Time message received.
                #rs_ts = datetime(rs_ts, 'Format', 'yyMMdd:HHmmss')
                rs_ts = [x.timeStamp for x in rs if x.record == 0]
                rs_ts = rs_ts[0]
            else:
                rs_ts = dt

            # Same as above, but now for calculated, prepared TransactiveRecord
            # message ms in the indexed active time interval.
            #ms = ismember({self.mySignal.timeInterval}, time_intervals(i).name)  # an array of logicals
            #ms = self.mySignal(ms)  # TransactiveRecords prepared in the indexed TimeInterval
            ms = [x for x in self.mySignal if x.timeInterval == time_intervals[i].name]

            if len(ms) > 0:  # if ~isempty(ss)
                #ms_ts = ms([rs.record] == 0).timeStamp  # Time message received.
                #ms_ts = datetime(ms_ts, 'Format', 'yyMMdd:HHmmss')
                ms_ts = [x.timeStamp for x in ms if x.record == 0]
                ms_ts = ms_ts[0]
            else:
                ms_ts = dt

            # Now, work through the convergence criteria.
            if len(ss) == 0:  # if isempty(ss):
                # No signal has been sent in this time interval. This is the
                # first convergence requirement. Set the convergence flag false.
                flag = False

            # received and received AFTER last sent and there is a big diff b/w ss and rs
            elif len(rs)>0 and rs_ts > ss_ts and are_different1(ss, rs, self.convergenceThreshold):
                # One or more TransactiveRecord objects has been received in the
                # indexed time interval and it has been received AFTER the last
                # time a message was sent. These are preconditions for the second
                # convergence requirement. Function are_different1() checks
                # whether the sent and received signals differ significantly. If
                # all these conditions are true, the Neighbor is not converged.
                flag = False
            elif dt - ss_ts > timedelta(minutes=5) and are_different2(ms, ss, self.convergenceThreshold):
                # Delay 5 min after last send AND
                # More than 5 minutes have passed since the last time a signal
                # was sent. This is a precondition to the third convergence
                # criterion. Function are_different2() returns true if mySignal
                # (ms) and the sentSignal (ss) differ significantly, meaning that
                # local conditions have changed enough that a new, revised signal
                # should be sent.
                flag = False


            # Check whether a convergence flag exists in the indexed time
            # interval.
            #iv = findobj(self.convergenceFlags, 'timeInterval', time_intervals(i))
            iv = find_obj_by_ti(self.convergenceFlags, time_intervals[i])

            if iv is None:  # if isempty(iv):

                # No convergence flag was found in the indexed time interval.
                # Create one and append it to the list.
                iv = IntervalValue(self, time_intervals(i), mkt, MeasurementType.ConvergenceFlag, flag)
                self.convergenceFlags.append(iv)

            else:

                # A convergence flag was found to exist in the indexed time
                # interval. Simply reassign it.
                iv.value = flag
        
        # If any of the convergence flags in active time intervals is false, the
        # overall convergence flag should be set false, too. Otherwise, true,
        # meaning the coordination sub-problem is converged with this Neighbor.
        if any([x.value for x in self.convergenceFlags]):
            self.converged = True
        else:
            self.converged = False

    def marginal_price_from_vertices(self, power, vertices):
        # FUNCTION MARGINAL_PRICE_FROM_VERTICES() - Given a power, determine the
        # corresponding marginal price from a set of supply- or demand-curve
        # vertices.
        #
        # INPUTS:
        # power - scheduled power [avg.kW]
        # vertices - array of supply- or demand-curve vertices
        #
        # OUTPUTS:
        # mp - a marginal price that corresponds to p [$/kWh]

        # Sort the supplied vertices by power and marginal price.
        vertices = order_vertices(vertices)

        # number of supplied vertices len
        v_len = len(vertices)

        if power < vertices[0].power:

            # The power is below the first vertex. Marginal price is
            # indeterminate. Assign the marginal price of the first vertex,
            # create a warning, and return. (This should be an unlikely
            # condition.)
            # warning('power was lower than first vertex')
            marginal_price = vertices[0].marginalPrice  # price [$/kWh]
            return marginal_price

        elif power >= vertices[-1].power:

            # The power is above the last vertex. Marginal price is
            # indeterminate. Assign the marginal price of the last vertex, create
            # a warning, and return. (This should be an unlikely condition.)
            # warning('power was greater than last vertex')
            marginal_price = vertices[-1].marginalPrice  # price [$/kWh]
            return marginal_price

        # There are multiple vertices v. Index through them.
        for i in range(v_len-1):  # for i = 1:(len - 1)
            if vertices[i].power <= power < vertices[i+1].power:
                # The power lies on a segment between two defined vertices.
                if vertices[i].power == vertices[i+1].power:
    
                    # The segment is horizontal. Marginal price is indefinite.
                    # Assign the marginal price of the second vertex and return.
                    _log.warning('segment is horizontal')
                    marginal_price = vertices[i+1].marginalPrice
                    return marginal_price
                else:
    
                    # The segment is not horizontal. Interpolate on the segment.
                    # First, determine the segment's slope.
                    slope = (vertices[i+1].marginalPrice 
                             - vertices[i].marginalPrice) / (vertices[i+1].power - vertices[i].power)  # [$/kWh/kW]

                    # Then interpolate to find marginal price.
                    marginal_price = vertices[i].marginalPrice + (power - vertices[i].power) * slope  # [$/kWh]
                    # catch 0 * inf cases
                    if power == vertices[i].power:
                        marginal_price = vertices[i].marginalPrice

                    return marginal_price

    def prep_transactive_signal(self, mkt, mtn):
        # PREP_TRANSACTIVE_SIGNAL() - Prepare transactive records to send
        # to a transactive neighbor. The prepared transactive signal should
        # represent the residual flexibility offered to the transactive neighbor in
        # the form of a supply or demand curve.
        # NOTE: the flexibility of the prepared transactive signals refers to LOCAL
        # value. Therefore this method does not make modifications for power losses
        # or demand charges, both of which are being modeled as originating with
        # the RECIPIENT of power.
        # FUTURE: The numbers of vertices may be restricted to emulate various
        # auction mechanisms.
        #
        # ASSUMPTIONS:
        # - The local system has converged, meaning that all asset and neighbor
        # powers have been calculated
        # - Neighbor and asset demand and supply curves have been updated and are
        # accurate. Active vertices will be used to prepare transactive
        # records.
        #
        # INPUTS:
        # tnm - Transactive NeighborModel object - target node to which a
        # transactive signal is to be sent
        # mkt - Market object
        # mtn - myTransactiveNode object
        #
        # OUTPUTS:
        # - Updates mySignal property, which contains transactive records that
        # are ready to send to the transactive neighbor

        # Ensure that object tnm is a transactive neighbor object.
        # if ~isa(tnm, 'NeighborModel')
        if not self.transactive:
            _log.warning('NeighborModel must be transactive')
            return

        # Gather active time intervals.
        time_intervals = mkt.timeIntervals  # active TimeInterval objects

        # gather market energy types
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Index through active time intervals.
        for i in range(len(time_intervals)):  # for i = 1:len(time_intervals)

            for i_energy_type in range(n_energy_types):
                # find the index for the energy type in this node
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal
                
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                else:
                    continue
                # Keep only the transactive records that are NOT in the indexed time
                # interval. The ones in the indexed time interval shall be recreated
                # in this iteration.
                #index = ~ismember([tnm.mySignal.timeInterval], time_intervals[i].name)
                # a logical aray
                #tnm.mySignal = tnm.mySignal(index)  # transactive records
                self.mySignal[my_energy_type] = [x for x in self.mySignal[my_energy_type] if x.timeInterval != time_intervals[i].name]

                # Create the vertices of the net supply or demand curve, EXCLUDING
                # this transactive neighbor (i.e., "tnm"). NOTE: It is important that
                # the transactive neighbor is excluded.
                #vertices = mkt.sum_vertices(mtn, time_intervals[i], tnm)  # Vertices
                vertices = mkt.sum_vertices(mtn, time_intervals[i], this_energy_type, self)  # Vertices

                # Find the minimum and maximum powers from the vertices. These are
                # soft constraints that represent a range of flexibility. The range
                # will usually be excessively large from the supply side much
                # smaller from the demand side.
                #vertex_powers = [vertices.power]  # [avg.kW]
                vertex_powers = [x.power for x in vertices]  # [avg.kW]

                maximum_vertex_power = max(vertex_powers)  # [avg.kW]
                minimum_vertex_power = min(vertex_powers)  # [avg.kW]

                # Find the transactive Neighbor's (i.e., "tnm") scheduled power in
                # the indexed time interval.
                #scheduled_power = findobj(tnm.scheduledPowers, 'timeInterval', time_intervals[i])  # an IntervalValue
                #scheduled_power = scheduled_power(1).value  # [avg.kW]
                scheduled_power = find_obj_by_ti(self.scheduledPowers[my_energy_type], time_intervals[i])
                scheduled_power = scheduled_power.value

                # Because the supply or demand curve of this transactive neighbor
                # model was excluded, an offset is created between it and the one
                # that had included the neighbor. The new balance point is mirrored
                # equal to, but of opposite sign from, the scheduled power.
                offset = -2 * scheduled_power  # [avg.kW]

                ## Record #0: Balance power point
                # Find the marginal price of the modified supply or demand curve that
                # corresponds to the balance point.
                try:
                    marginal_price_0 = self.marginal_price_from_vertices(scheduled_power + offset, vertices)
                except:
                    _log.warning('erros/warnings with object ' + self.name)


                # Create transactive record #0 to represent that balance point, and
                # populate its properties.
                # NOTE: A TransactiveRecord constructor is being used.
                transactive_record = TransactiveRecord(time_intervals[i], 0, marginal_price_0, scheduled_power + offset, e_type=this_energy_type)

                # Append the transactive signal to those that are ready to be sent.
                #tnm.mySignal = [tnm.mySignal, transactive_record]
                self.mySignal[my_energy_type].append(transactive_record)

                if len(vertices) > 1:  # if len(vertices) > 1

                    ## Transactive Record #1: Minimum neighbor power
                    # Find the minimum power. For transactive neighbors, the minimum may
                    # be based on the physical constraint of the line between neighbors.
                    # A narrower range may be used if the full range is infeasible. For
                    # example, it might not be feasible for a neighbor to change from a
                    # power importer to exporter, given it limited generation resources.
                    # NOTE: Power is a signed quantity. The maximum power may be 0 or
                    # even negative.
                    minimum_power = self.object.minimumPower  # power [avg.kW]
                    minimum_power = max(minimum_power, minimum_vertex_power - offset)

                    # Find the marginal price on the modified net suppy or demand curve
                    # that corresponds to the minimum power, plus its offset.
                    marginal_price_1 = self.marginal_price_from_vertices(minimum_power + offset, vertices)  # marginal price [$/kWh]

                    # Create transactive record #1 to represent the minimum power, and
                    # populate its properties.
                    # NOTE: A TransactiveRecord constructor is being used.
                    transactive_record = TransactiveRecord(time_intervals[i], 1, marginal_price_1, minimum_power + offset, e_type=this_energy_type)

                    # Append the transactive signal to those that are ready to be sent.
                    #tnm.mySignal = [tnm.mySignal, transactive_record]
                    self.mySignal[my_energy_type].append(transactive_record)

                    ## Transactive Record #2: Maximum neighbor power
                    # Find the maximum power. For transactive neighbors, the maximum may
                    # be based on the physical constraint of the line between neighbors.
                    # NOTE: Power is a signed quantity. The maximum power may be 0 or
                    # even negative.
                    maximum_power = self.object.maximumPower  # power [avg.kW]
                    maximum_power = min(maximum_power, maximum_vertex_power - offset)

                    # Find the marginal price on the modified net supply or demand curve
                    # that corresponds to the neighbor's maximum power p, plus its
                    # offset.
                    marginal_price_2 = self.marginal_price_from_vertices(maximum_power + offset, vertices)  # price [$/kWh]

                    # Create Transactive Record #2 and populate its properties.
                    # NOTE: A TransactiveRecord constructor is being used.
                    transactive_record = TransactiveRecord(time_intervals[i], 2, marginal_price_2, maximum_power + offset, e_type =this_energy_type)

                    # Append the transactive signal to the list of transactive signals
                    # that are ready to be sent to the transactive neighbor.
                    #tnm.mySignal = [tnm.mySignal, transactive_record]
                    self.mySignal[my_energy_type].append(transactive_record)  # transactive records

                    ## Additional Transactive Records: Search for included vertices.
                    # Some of the vertices of the modified net supply or demand curve may lie
                    # between the vertices that have been defined. These additional vertices
                    # should be included to correctly convey the system's flexibiltiy to its
                    # neighbor.
                    # Create record index counter index. This must be incremented before
                    # adding a transactive record.
                    index = 2

                    # Index through the vertices of the modified net supply or demand
                    # curve to see if any of their marginal prices lie within the
                    # vertices that have been defined for this neighbor's miminum power
                    # (at marginal_price_1) and maximum power (at marginal_price_2).
                    for j in range(len(vertices)-1):  # for j = 1:(len(vertices) - 1)

                        if marginal_price_1 < vertices[j].marginalPrice < marginal_price_2:

                            # The vertex lies in the range defined by this neighbor's
                            # minimum and maximum power range and corresponding marginal
                            # prices and should be included.

                            # Create a new transactive record and assign its propteries.
                            # See struct TransactiveRecord. NOTE: The vertex already
                            # resided on the modified net supply or demand curve and does
                            # not need to be offset.
                            # NOTE: A TransactiveRecord constructor is being used.
                            index = index + 1  # new transactive record number
                            transactive_record = TransactiveRecord(time_intervals[i], 
                                                                index, 
                                                                vertices[j].marginalPrice,
                                                                vertices[j].power, e_type=this_energy_type)

                            # Append the transactive record to the list of transactive
                            # records that are ready to send.
                            #tnm.mySignal = [tnm.mySignal, transactive_record]
                            self.mySignal[my_energy_type].append(transactive_record)

    def receive_transactive_signal(self, mtn):
        # FUNCTION RECEIVE_TRANASCTIVE_SIGNAL() - receive and save transactive
        # records from a transactive Neighbor object. 
        # (NOTE: In the Matlab implementation, the transactive signals are
        # "received" via a readable csv file.)
        # mtn = myTransactiveNode object
        # obj - the NeighborModel object
        #
        # The process of receiving a transactive signal is emulated by reading an
        # available text table that is presumed to have been created by the
        # transactive neighbor. This process may change in field settings and using
        # Python and other code environments.
        
        # If trying to receive a transactive signal from a non-transactive neighbor,
        # create a warning and return.
        if not self.transactive:
            _log.warning('Transactive signals are not expected to be received from non-transactive neighbors. '
                         'No signal is read.')
            return
        
        # Here is the format for the preferred text filename. (NOTE: The name is
        # applied by the transactive neighbor and is not under the direct control
        # of myTransactiveNode.)
        # The filename starts with a shortened name of the originating node.
        source_node = str(self.object.name)
        if len(source_node) > 5:
            source_node = source_node[0:5]  # source_node(1:5)
        
        # Shorten the name of the target node
        target_node = str(mtn.name)
        if len(target_node) > 5:
            target_node = target_node[0:5]  # target_node(1:5)
        
        # Format the filename. Do not allow spaces.
        filename = ''.join([source_node, '-', target_node, '.txt'])
        filename = filename.replace(' ', '')
        #filename = 'Python/'+filename

        # Read the signal, a set of csv records
        #try:
        #  T = readtable(filename)
        #except:
        #  _log.warning("no signal file found for %s." % self.name)
        #  return
        #[r, ~] = size(T)
        #T = table2struct(T)
        with open(filename) as file:
            reader = csv.DictReader(file)

            # Extract the interval information into transactive records.
            # NOTE: A TransactiveRecord constructor is being used.
            for row in reader:  # for i = 1:r
                if 'E_Type' in row:
                    transactive_record = TransactiveRecord(ti=row['TimeInterval'],
                                                      rn=int(row['Record']),
                                                      mp=float(row['MarginalPrice']),
                                                      p=float(row['Power']),
                                                      pu=float(row['PowerUncertainty']),
                                                      cost=float(row['Cost']),
                                                      rp=float(row['ReactivePower']),
                                                      rpu=float(row['ReactivePowerUncertainty']),
                                                      v=float(row['Voltage']),
                                                      vu=float(row['VoltageUncertainty']),
                                                      e_type=int(row['E_Type']))
                else:
                    transactive_record = TransactiveRecord(ti=row['TimeInterval'],
                                                        rn=int(row['Record']),
                                                        mp=float(row['MarginalPrice']),
                                                        p=float(row['Power']),
                                                        pu=float(row['PowerUncertainty']),
                                                        cost=float(row['Cost']),
                                                        rp=float(row['ReactivePower']),
                                                        rpu=float(row['ReactivePowerUncertainty']),
                                                        v=float(row['Voltage']),
                                                        vu=float(row['VoltageUncertainty']))

                # Save each transactive record (NOTE: We can apply more savvy to find
                # and replace the signal later.)
                #self.receivedSignal = [self.receivedSignal, transative_record]
                self.receivedSignal.append(transactive_record)

    ## SEALED - DONOT MODIFY
    ## schedule() - have object schedule its power in active time intervals
    def schedule(self, mkt):
        # If the object is a NeighborModel give its vertices priority
        self.update_vertices(mkt)
        self.schedule_power(mkt)

        # Have the objects estimate their available reserve margin
        self.calculate_reserve_margin(mkt)

    def schedule_power(self, mkt):
        # FUNCTION SCHEDULE_POWER() Calculate power for each time interval
        #
        # This is a basic method for calculating power generation of consumption in
        # each active time interval. It infers power
        # generation or consumption from the supply or demand curves that are
        # represented by the neighbor's active vertices in the active time
        # intervals.
        #
        # This strategy should is anticipated to work for most neighbor model
        # objects. If additional features are needed, child neighbor models must be
        # created and must redefine this method.
        #
        # PRESUMPTIONS:
        # - All active vertices have been created and updated.
        # - Marginal prices have been updated and exist for all active intervals.
        #
        # INPUTS:
        # obj - Local asset model object
        # mkt - Market object
        #
        # OUTPUTS:
        # updates array self.scheduledPowers
        
        # Gather the active time intervals ti
        time_intervals = mkt.timeIntervals  # TimeInterval objects

        # gather energy types
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1
        
        # Index through active time intervals ti
        for i in range(len(time_intervals)):  # for i = 1:len(time_intervals)
            # index through the energy types on the market
            for i_energy_type in range(n_energy_types):
                if hasattr(mkt, 'measurementType'):
                    this_energy_type = mkt.measurementType[i_energy_type]
                else:
                    this_energy_type = MeasurementType.PowerReal
                # check to see if this neighbor has that energy type
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                # if not, then move on to the next energy type
                else:
                    continue
        
                # Find the marginal price for the indexed time interval
                #marginal_price = findobj(mkt.marginalPrices, 'timeInterval', time_intervals[i])  # an IntervalValue
                # Extract its marginal price value
                #marginal_price = marginal_price(1).value  # [$/kWh]
                marginal_price = find_obj_by_ti(mkt.marginalPrices[i_energy_type], time_intervals[i])  # an IntervalValue
                marginal_price = marginal_price.value

                # Find the power that corresponds to the marginal price according
                # to the set of active vertices in the indexed time interval.
                # Function Production() works for any power that is determined by
                # its supply curve or demand curve, as represented by the object's
                # active vertices.
                value = production(self, marginal_price, time_intervals[i], energy_type=this_energy_type)  # [avg. kW]

                # Check to see if a scheduled power already exists in the indexed
                # time interval
                #interval_value = findobj(self.scheduledPowers, 'timeInterval', time_intervals[i])  # an IntervalValue
                interval_value = find_obj_by_ti(self.scheduledPowers[my_energy_type], time_intervals[i])  # an IntervalValue

                if interval_value is None:

                    # No scheduled power was found in the indexed time interval.
                    # Create the interval value and assign it the scheduled power
                    #interval_value = IntervalValue(self, time_intervals[i], mkt, 'ScheduledPower', value)  # an IntervalValue
                    interval_value = IntervalValue(self, time_intervals[i], mkt,
                                                MeasurementType.ScheduledPower,
                                                value)  # an IntervalValue

                    # Append the scheduled power to the list of scheduled powers
                    #self.scheduledPowers = [self.scheduledPowers, interval_value]
                    self.scheduledPowers[my_energy_type].append(interval_value)  # IntervalValue objects

                else:

                    # A scheduled power already exists in the indexed time interval.
                    # Simply reassign its value.
                    interval_value.value = value  # [avg. kW]

    def schedule_engagement(self):
        # SCHEDULE_ENGAGEMENT() - required from AbstractModel, but not particularly
        # useful for any NeighborModel.
        return

    def send_transactive_signal(self, mtn):
        # SEND_TRANSACTIVE_SIGNAL() - send transactive records to a transactive
        # Neighbor.
        # (NOTE: In the Matlab implementation, "sending" is the creation of a csv
        # file that could be made available to the transactive Neighbor.)
        #
        # Retrieves the current transactive records, formats them into a table, and
        # "sends" them to a text file for the transactive neighbor. The property
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
        # obj - NeighborModel object
        # mtn - myTransactiveNode object

        # If neighbor is non-transactive, warn and return. Non-transactive
        # neighbors do not communicate transactive signals.
        if not self.transactive:
            _log.warning(['Non-transactive neighbors do not send transactive signals. No signal is sent to', self.name, '.'])
            return

        # Collect current transactive records concerning myTransactiveNode.
        # accomodate possibility of multiple energy types therefore multiple energy signals
        if isinstance(self.mySignal, list):
            tr = [signal for e_list in self.mySignal for signal in e_list]
        # if you only have one energy type and they are not separated then that is okay too
        else:
            tr = self.mySignal

        # Number of records in mySignal len 
        tr_len = len(tr)
        
        if tr_len == 0:  # No signal records are ready to send
            _log.warning("No transactive records were found. No transactive signal can be sent to %s." % self.name)
            return

        # Send the signal. For this Matlab version, the sending is emulated by
        # creating a table file that could be read by another active process.
        
        # Generate a meaningful filename from source node name src and target
        # node name tgt. 
        source_node = str(mtn.name)
        if len(source_node) > 5:
            source_node = source_node[0:5]  # source_node(1:5)
        
        target_node = str(self.object.name)
        if len(target_node) > 5:
            target_node = target_node[0:5]  # target_node(1:5)
    
        # Format the output filename.
        #filename = strcat([source_node, '-', target_node, '.txt'])
        filename = ''.join([source_node, '-', target_node, '.txt'])
        filename = filename.replace(' ', '')

        # And write the table
        lines = [
            "E_Type,TimeStamp,TimeInterval,Record,MarginalPrice,Power,PowerUncertainty,Cost,ReactivePower,ReactivePowerUncertainty,Voltage,VoltageUncertainty"
        ]
        for i in range(tr_len):  # for i = 1:len
            lines.append(','.join([
                str(tr[i].e_type),
                str(tr[i].timeStamp),
                str(tr[i].timeInterval),
                str(tr[i].record),
                str(tr[i].marginalPrice),
                str(tr[i].power),
                str(tr[i].powerUncertainty),
                str(tr[i].cost),
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
        #mtr = findobj(self.meterPoints, 'MeasturementType', MeasurementType.AverageDemandkW)  # a MeterPoint object
        mtr = [x for x in self.meterPoints if x.measurementType == MeasurementType.AverageDemandkW]
        mtr = mtr[0] if len(mtr) > 0 else None

        # find the index for real power
        # this method assumes there are only demand charges for real power
        i_real_power = -1
        if hasattr(self, 'measurementType'):
            i_real_power = self.measurementType.index(MeasurementType.PowerReal)

        if mtr is None:

            # No appropriate MeterPoint object was found. The demand threshold
            # must be inferred.

            # Gather the active time intervals ti and find the current (soonest) one.
            ti = mkt.timeIntervals
            #[~, ind] = sort([ti.startTime])
            #ti = ti(ind)  # ordered time intervals from soonest to latest
            ti.sort(key=lambda x: x.startTime)

            # Find current demand d that corresponds to the nearest time
            # interval.
            #d = findobj(self.scheduledPowers, 'timeInterval', ti(1))  # [avg.kW]
            if i_real_power>=0:
                d = find_obj_by_ti(self.scheduledPowers[i_real_power], ti[0])

            # Update the inferred demand.
            self.demandThreshold = max([0, self.demandThreshold[i_real_power], d.value])  # [avg.kW]

        else:

            # An appropriate MeterPoint object was found. The demand threshold
            # may be updated from the MeterPoint object.

            # Update the demand threshold.
            self.demandThreshold[i_real_power] = max([0, self.demandThreshold[i_real_power], mtr.currentMeasurement])  # [avg.kW]

        # The demand threshold should be reset in a new month. First find the current month number mon.
        mon = datetime.today().month

        if mon != self.demandMonth:
            # This must be the start of a new month. The demand threshold must be
            # reset. For now, "resetting" means using a fraction (e.g., 80#) of
            # the final demand threshold in the prior month.
            self.demandThreshold[i_real_power] = 0.8 * self.demandThreshold[i_real_power]
            self.demandMonth = mon

    def update_dual_costs(self, mkt):

        # Gather the active time intervals.
        time_intervals = mkt.timeIntervals  # active TimeInterval objects

        # gather the energy types on the market
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Index through the time intervals.
        for i in range(len(time_intervals)):  # for i = 1:len(time_intervals)

            # index through the energy types
            for i_energy_type in range(n_energy_types):
                this_energy_type = mkt.measurementType[i_energy_type]

                # if this neighbor transacts the energy type on the market, then find the marginal prices
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                # if this neighbor does not transact with that type of energy, then go to the next type
                else:
                    continue

                # Find the marginal price mp for the indexed time interval in the
                # given market
                #marginal_price = findobj(mkt.marginalPrices, 'timeInterval', time_intervals[i])  # an IntervalValue
                #marginal_price = marginal_price(1).value  # a marginal price [$/kWh]
                marginal_price = find_obj_by_ti(mkt.marginalPrices[i_energy_type], time_intervals[i])
                marginal_price = marginal_price.value

                # Find the scheduled power for the neighbor in the indexed time
                # interval.
                #scheduled_power = findobj(self.scheduledPowers, 'timeInterval', time_intervals[i])  # an IntervalValue
                #scheduled_power = scheduled_power(1).value  # [avg.kW]
                scheduled_power = find_obj_by_ti(self.scheduledPowers[my_energy_type], time_intervals[i])
                scheduled_power = scheduled_power.value

                # Find the production cost in the indexed time interval.
                #production_cost = findobj(self.productionCosts, 'timeInterval', time_intervals[i])  # an IntervalValue
                #production_cost = production_cost(1).value  # production cost [$]
                production_cost = find_obj_by_ti(self.productionCosts[my_energy_type], time_intervals[i])
                production_cost = production_cost.value

                # Dual cost in the time interval is calculated as production cost,
                # minus the product of marginal price, scheduled power, and the
                # duration of the time interval.
                #interval_duration = time_intervals[i].duration
                #if isduration(interval_duration):
                    # NOTE: Matlab function hours() toggles duration to numeric and
                    # is correct here.
                    #interval_duration = hours(interval_duration)
                interval_duration = get_duration_in_hour(time_intervals[i].duration)

                dual_cost = production_cost - (marginal_price * scheduled_power * interval_duration)  # a dual cost [$]

                # Check whether a dual cost exists in the indexed time interval
                #interval_value = findobj(self.dualCosts, 'timeInterval', time_intervals[i])  # an IntervalValue
                interval_value = find_obj_by_ti(self.dualCosts[my_energy_type], time_intervals[i])

                if interval_value is None:  # if isempty(interval_value)

                    # No dual cost was found in the indexed time interval. Create an
                    # interval value and assign it the calculated value.
                    interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.DualCost, dual_cost)  # an IntervalValue

                    # Append the new interval value to the list of active interval values.
                    #self.dualCosts = [self.dualCosts, interval_value]  # IntervalValue objects
                    self.dualCosts[my_energy_type].append(interval_value)

                else:

                    # The dual cost value was found to already exist in the indexed
                    # time interval. Simply reassign it the new calculated value.
                    interval_value.value = dual_cost  # a dual cost [$]
        self.totalDualCost = 0.0
        for my_energy_type in range(len(self.measurementType)):
            # Ensure that only active time intervals are in the list of dual costs.
            #active_dual_costs = ismember([self.dualCosts.timeInterval], time_intervals)  # a logical array
            #self.dualCosts = self.dualCosts(active_dual_costs)  # IntervalValue objects
            self.dualCosts[my_energy_type] = [x for x in self.dualCosts[my_energy_type] if x.timeInterval in time_intervals]

            # Sum the total dual cost and save the value
            self.totalDualCost = self.totalDualCost + sum([x.value for x in self.dualCosts[my_energy_type]])  # total dual cost [$]

    def update_production_costs(self, mkt):

        # Gather active time intervals
        time_intervals = mkt.timeIntervals  # active TimeInterval objects

        # gather the types of energy on the market
        if hasattr(mkt, 'measurementType'):
            n_energy_types = len(mkt.measurementType)
        else:
            n_energy_types = 1

        # Index through the active time intervals
        for i in range(len(time_intervals)):  # for i = 1:len(time_intervals)
            # index through the energy types
            for i_energy_type in range(n_energy_types):
                this_energy_type = mkt.measurementType[i_energy_type]

                # if this neighbor transacts the energy type on the market, then find the marginal prices
                if this_energy_type in self.measurementType:
                    my_energy_type = self.measurementType.index(this_energy_type)
                # if this neighbor does not transact with that type of energy, then go to the next type
                else:
                    continue

                # Get the scheduled power in the indexed time interval.
                #scheduled_power = findobj(self.scheduledPowers, 'timeInterval', time_intervals[i])  # an IntervalValue
                #scheduled_power = scheduled_power(1).value  # [avg.kW]
                scheduled_power = find_obj_by_ti(self.scheduledPowers[my_energy_type], time_intervals[i])
                scheduled_power = scheduled_power.value

                # Call on function that calculates production cost pc based on the
                # vertices of the supply or demand curve.
                production_cost = prod_cost_from_vertices(self, time_intervals[i], scheduled_power, market=mkt, energy_type = this_energy_type)  # interval production cost [$]

                # Check to see if the production cost value has been defined for the
                # indexed time interval.
                #interval_value = findobj(self.productionCosts, 'timeInterval', time_intervals[i])  # an IntervalValue
                interval_value = find_obj_by_ti(self.productionCosts[my_energy_type], time_intervals[i])

                if interval_value is None:  # if isempty(interval_value)

                    # The production cost value has not been defined in the indexed
                    # time interval. Create it and assign its value pc.
                    #interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ProductionCost, production_cost)  # an IntervalValue
                    interval_value = production_cost
                    # Append the production cost to the list of active production
                    # cost values.
                    #self.productionCosts = [self.productionCosts, interval_value]  # IntervalValue objects
                    self.productionCosts[my_energy_type].append(interval_value)
                else:

                    # The production cost value already exists in the indexed time
                    # interval. Simply reassign its value.
                    interval_value.value = production_cost.value  # production cost [$]

        self.totalProductionCost = 0.0
        for my_energy_type in range(len(self.measurementType)):
            # Ensure that only active time intervals are in the list of active
            # production costs.
            #active_production_costs = ismember([self.productionCosts.timeInterval], time_intervals)  # a logical array
            #self.productionCosts = self.productionCosts(active_production_costs)  # IntervalValue objects
            self.productionCosts[my_energy_type] = [x for x in self.productionCosts[my_energy_type] if x.timeInterval in time_intervals]

            # Sum the total production cost.
            #self.totalProductionCost = sum([self.productionCosts.value])  # total production cost [$]
            self.totalProductionCost = self.totalProductionCost + sum([x.value for x in self.productionCosts[my_energy_type]])  # total production cost [$]

    def update_vertices(self, mkt):
        # UPDATE_VERTICES() - Update the active vertices that define Neighbors'
        # residual flexibility in the form of supply or demand curves.
        #
        # The active vertices of non-transactive neighbors are relatively constant.
        # Active vertices must be created for new active time intervals. Vertices
        # may be affected by demand charges, too, as new demand-charge thresholds
        # are becoming established.
        #
        # The active vertices of transactive neighbors are also relatively
        # constant. New vertices must be created for new active time intervals. But
        # active vertices must also be checked and updated whenever a new
        # transactive signal is received.
        #
        # PRESUMPTIONS:
        # - time intervals are up-to-date
        # - at least one default vertex has been defined, should all other
        # efforts to establish meaningful vertices fail
        #
        # INPUTS:
        # obj - Neighbor model object
        # mkt - Market object
        #
        # OUTPUTS:
        # Updates self.activeVertices - an array of IntervalValues that contain
        # Vertex() structs

        # Extract active time intervals
        time_intervals = mkt.timeIntervals  # active TimeInterval objects

        # Delete any active vertices that are not in active time intervals. This
        # prevents time intervals from accumulating indefinitely.
        #active_vertices = ismember([self.activeVertices.timeInterval], time_intervals)  # a logical array
        #self.activeVertices = self.activeVertices(active_vertices)  # IntervalValue objects
        if hasattr(self, 'measurementType'):
            n_energy_types = len(self.measurementType)
            for i in range(n_energy_types):
                self.activeVertices[i] = [x for x in self.activeVertices[i] if x.timeInterval in time_intervals]
        else:
            self.activeVertices = [x for x in self.activeVertices if x.timeInterval in time_intervals]

        # Index through active time intervals
        for i in range(len(time_intervals)):  # for i = 1:len(time_intervals)
            for i_energy_type in range(n_energy_types):

                # Keep active vertices that are not in the indexed time interval, but
                # discard the one(s) in the indexed time interval. These shall be
                # recreated in this iteration.
                # (NOTE: This creates some unnecessary recalculation that might be
                # fixed in the future.)
                #active_vertices = ~ismember([self.activeVertices.timeInterval], time_intervals[i])  # a logical array
                #self.activeVertices = self.activeVertices(active_vertices)  # IntervalValue objects
                self.activeVertices[i_energy_type] = [x for x in self.activeVertices[i_energy_type] if x.timeInterval != time_intervals[i]]

                # Get the default vertices.
                default_vertices = self.defaultVertices[i_energy_type]  # [self.defaultVertices]

                if len(default_vertices) == 0:  # if isempty(default_vertices):

                    # No default vertices are found. Warn and return.
                    _log.warning( 'At least one default vertex must be defined for neighbor model object %s. '
                                'Scheduling was not performed' % (self.name) )
                    return

                if not self.transactive:  # Neighbor is non-transactive

                    # Default vertices were found. Index through the default vertices.
                    for k in range(len(default_vertices)):  #for k = 1:len(default_vertices)

                        # Get the indexed default vertex.
                        value = default_vertices[k]

                        # Create an active vertex interval value in the indexed time
                        # interval.
                        interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, value)

                        # Append the active vertex to the list of active vertices
                        self.activeVertices[i_energy_type].append(interval_value)


                elif self.transactive:  # a transactive neighbor

                    # Check for transactive records in the indexed time interval.
                    #received_vertices = findobj([self.receivedSignal], 'timeInterval', time_intervals[i].name)
                    received_vertices = [x for x in self.receivedSignal if x.timeInterval == time_intervals[i].name]

                    if len(received_vertices) == 0:  #if isempty(received_vertices)

                        # No received transactive records address the indexed time
                        # interval. Default value(s) must be used.

                        # Default vertices were found. Index through the default
                        # vertices.
                        for k in range(len(default_vertices)):  # for k = 1:len(default_vertices)

                            # Get the indexed default vertex
                            value = default_vertices[k]

                            # Create an active vertex interval value in the indexed
                            # time interval
                            if not isinstance(value, IntervalValue):
                                interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, value)  # an IntervalValue
                            else:
                                interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, value.value)  # an IntervalValue
                            # Append the active vertex to the list of active
                            # vertices.
                            #self.activeVertices = [self.activeVertices, interval_value]  # IntervalValue objects
                            self.activeVertices[i_energy_type].append(interval_value)
                    else:

                        # One or more transactive records have been received
                        # concerning the indexed time interval. Use these to
                        # re-create active Vertices.

                        # Sort the received_vertices (which happen to be
                        # TransactiveRecord objects) by increasing price and power.
                        #[~, index] = sort([received_vertices.power])
                        #received_vertices = received_vertices(index)
                        #[~, index] = sort([received_vertices.marginalPrice])
                        #received_vertices = received_vertices(index)
                        received_vertices = order_vertices(received_vertices)

                        # Prepare for demand charge vertices.

                        # This flag will be replace by its preceding ordered vertex
                        # index if any of the vertices are found to exceed the
                        # current demand threshold.
                        demand_charge_flag = 0  # simply a flag

                        # The demand-charge threshold is based on the actual measured
                        # peak this month, but it may also be superseded in predicted
                        # time intervales prior to the currently indexed one.
                        # Start with the metered demand threshold
                        demand_charge_threshold = self.demandThreshold[i_energy_type]  # [avg.kW]

                        # Calculate the peak in time intervals that come before the
                        # one now indexed by i.
                        # Get all the scheduled powers.
                        prior_power = self.scheduledPowers[i_energy_type]  # [avg.kW]

                        if len(prior_power) < i+1:  #if length(prior_power) < i

                            # Especially the first iteration can encounter missing
                            # scheduled power values. Place these out of the way by
                            # assigning then as small as possible. The current demand
                            # threshold will always trump this value.
                            prior_power = [float("-inf")]  # -inf

                        else:

                            # The scheduled powers look fine. Pick out the ones that
                            # are indexed prior to the currently indexed value.
                            #prior_power = [prior_power(1:i).value]  # [avg.kW]
                            prior_power = [x.value for x in prior_power[0:i+1]]


                        # Pick out the maximum power from the prior scheduled power values.
                        #predicted_prior_peak = max(prior_power, [], 'omitnan')  # [avg.kW]
                        predicted_prior_peak = max(prior_power)  # [avg.kW]

                        # The demand-charge threshold for the indexed time interval
                        # should be the larger of the current and predicted peaks.
                        #demand_charge_threshold = max([demand_charge_threshold, predicted_prior_peak], [], 'omitnan')  # [avg.kW]
                        demand_charge_threshold = max([demand_charge_threshold, predicted_prior_peak])  # [avg.kW]

                        # Index through the vertices in the received transactive
                        # records for the indexed time interval.
                        for k in range(len(received_vertices)):  # for k = 1:len(received_vertices)

                            # If there are multiple transactive records in the
                            # indexed time interval, we don't need to create a vertex
                            # for Record #0. Record #0 is the balance point, which
                            # must lie on existing segments of the supply or demand
                            # curve.
                            if len(received_vertices) >= 3 and received_vertices[k].record == 0:
                                continue  # jumps out of for loop to next iteration


                            # Create working values of power and marginal price from
                            # the received vertices.
                            power = received_vertices[k].power
                            marginal_price = received_vertices[k].marginalPrice

                            # If the Neighbor power is positive (importation of
                            # electricity), then the value may be affected by losses.
                            # The available power is diminished (compared to what was
                            # sent), and the effective marginal price is increased
                            # (because myTransactiveNode is paying for electricity
                            # that it does not receive).
                            if power > 0:
                                #factor1 = (power / self.object.maximumPower) ^ 2
                                factor1 = (power / self.object.maximumPower) ** 2
                                factor2 = 1 + factor1 * self.object.lossFactor
                                power = power / factor2
                                marginal_price = marginal_price * factor2

                                if power > demand_charge_threshold:

                                    # The power is greater than the anticipated
                                    # demand threshold. Demand charges are in play.
                                    # Set a flag.
                                    demand_charge_flag = k

                            # Create a corresponding (price,power) pair (aka "active
                            # vertex") using the received power and marginal price.
                            # See struct Vertex().
                            value = Vertex(marginal_price, received_vertices[k].cost, 
                                        power, received_vertices[k].powerUncertainty)  # a Vertex

                            # Create an active vertex interval value for the vertex
                            # in the indexed time interval.
                            interval_value = IntervalValue(self, time_intervals[i], mkt, 
                                                        MeasurementType.ActiveVertex, value)  # an IntervalValue

                            # Append the active vertex to the list of active vertices.
                            #self.activeVertices = [self.activeVertices, interval_value]  # IntervalValue objects
                            self.activeVertices[i_energy_type].append(interval_value)

                        # DEMAND CHARGES
                        # Check whether the power of any of the vertices was found to
                        # be larger than the current demand-charge threshold, as
                        # would be indicated by this flag being a value other than 0.
                        if demand_charge_flag != 0:

                            # Demand charges are in play.
                            # Get the newly updated active vertices for this
                            # transactive Neighbor again in the indexed time
                            # interval.
                            #vertices = findobj(self.activeVertices, 'timeInterval', time_intervals[i])  # IntervalValue objects
                            #vertices = [vertices.value]  # Vertex objects
                            vertices = [x.value for x in self.activeVertices[i_energy_type] if x.timeInterval == time_intervals[i]]


                            # Find the marginal price that would correspond to the
                            # demand-charge threshold, based on the newly updated
                            # (but excluding the effects of demand charges) active
                            # vertices in the indexed time interval.
                            marginal_price = self.marginal_price_from_vertices(demand_charge_threshold, vertices)  # [$/kWh]

                            # Create the first of two vertices at the intersection of
                            # the demand-charge threshold and the supply or demand
                            # curve from prior to the application of demand charges.
                            vertex = Vertex(marginal_price, 0, demand_charge_threshold)  # a Vertex object

                            # Create an IntervalValue for the active vertex.
                            interval_value = IntervalValue(self, time_intervals[i], mkt,
                                                        MeasurementType.ActiveVertex, vertex)  # an IntervalValue object

                            # Store the new active vertex interval value.
                            #self.activeVertices = [self.activeVertices, interval_value]  # IntervalValue objects
                            self.activeVertices[i_energy_type].append(interval_value)

                            # Create the marginal price of the second of the two new
                            # vertices, augmented by the demand rate.
                            marginal_price = marginal_price + self.demandRate[i_energy_type]  # [$/kWh]

                            # Create the second vertex.
                            vertex = Vertex(marginal_price, 0, demand_charge_threshold)  # a vertex object

                            # ... and the interval value for the second vertex,
                            interval_value = IntervalValue(self, time_intervals[i], mkt,
                                                        MeasurementType.ActiveVertex, vertex)  # an IntervalValue object

                            # ... and finally store the active vertex.
                            #self.activeVertices = [self.activeVertices, interval_value]  # IntervalValue objects
                            self.activeVertices[i_energy_type].append(interval_value)

                            # Check that vertices having power greater than the
                            # demand threshold have their marginal prices reflect the
                            # demand charges. Start by picking out those in the
                            # currently indexed time interval.
                            #interval_values = findobj(self.activeVertices, 'timeInterval', time_intervals[i])  # IntervalValue objects
                            interval_values = [x for x in self.activeVertices[i_energy_type] if x.timeInterval == time_intervals[i]]

                            # Index through the current active vertices in the
                            # indexed time interval. At this point, these include
                            # vertices from both prior to and after the introduction
                            # of demand-charge vertices.
                            for k in range(len(interval_values)):  #for k = 1:len(interval_values)

                                # Extract the indexed vertex.
                                vertex = interval_values[k].value

                                # Extract the power of the indexed vertex.
                                vertex_power = vertex.power  # [avg.kW]

                                if vertex_power > demand_charge_threshold:

                                    # The indexed vertex's power exceeds the
                                    # demand-charge threshold. Increment the vertex's
                                    # marginal price with the demand rate.
                                    vertex.marginalPrice = vertex.marginalPrice + self.demandRate[i_energy_type]

                                    # ... and re-store the vertex in its IntervalValue
                                    interval_values[k].value = vertex  # an IntervalValue object

                else:

                    # Logic should not arrive here. Error.
                    raise ('Neighbor %s must be either transactive or not.' % (self.name))


if __name__ == '__main__':
    NeighborModel()
