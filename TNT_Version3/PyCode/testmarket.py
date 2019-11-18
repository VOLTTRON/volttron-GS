# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# 'AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}



from datetime import datetime, timedelta

from model import Model
from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from interval_value import IntervalValue
from transactive_record import TransactiveRecord
from meter_point import MeterPoint
from market import Market
from market_state import MarketState
from time_interval import TimeInterval
from neighbor import Neighbor
from neighbor_model import NeighborModel
from local_asset import LocalAsset
from local_asset_model import LocalAssetModel
from myTransactiveNode import myTransactiveNode


def test_all():
    print('Running Market.test_all()')
    test_assign_system_vertices()  # High priority - test not complete
    test_balance()  # High priorty - test not completed
    test_calculate_blended_prices()  # Low priority - FUTURE
    test_check_intervals()  # High priorty - test not completed
    test_check_marginal_prices()  # High priorty - test not completed
    test_schedule()  # High priorty - test not completed
    test_sum_vertices()  # High priorty - test not completed
    test_update_costs()  # High priorty - test not completed
    test_update_supply_demand()  # High priorty - test not completed
    #test_view_net_curve()  # High priorty - test not completed
    #test_view_marginal_prices()  # High priority - test completed


def test_assign_system_vertices():
    print('Running Market.test_assign_system_vertices()')
    pf = 'test is not complete'

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_balance():
    print('Running Market.test_balance()')
    pf = 'test is not complete'

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_calculate_blended_prices():
    print('Running Market.test_calculate_blended_prices()')
    pf = 'test is not complete'

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_check_intervals():
    print('Running Market.test_check_intervals()')
    pf = 'test is not complete'

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_check_marginal_prices():
    print('Running Market.test_check_marginal_prices()')
    pf = 'test is not complete'

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_schedule():
    print('Running Market.test_schedule()')
    print('WARNING: This test may be affected by NeighborModel.schedule()')
    print('WARNING: This test may be affected by NeighborModel.schedule()')
    pf = 'pass'

    # Establish a myTransactiveNode object
    mtn = myTransactiveNode()

    # Establish a test market
    test_mkt = Market()

    # Create and store one TimeInterval
    dt = datetime(2018, 1, 1, 12, 0, 0)  # Noon Jan 1, 2018
    at = dt
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    st = dt
    ti = TimeInterval(at, dur, mkt, mct, st)

    test_mkt.timeIntervals = [ti]

    # Create and store a marginal price in the active interval.
    test_mkt.marginalPrices = [
        IntervalValue(test_mkt, ti, test_mkt, MeasurementType.MarginalPrice, 0.01)]

    print('- configuring a test Neighbor and its NeighborModel')
    # Create a test object that is a Neighbor
    test_obj1 = Neighbor()
    test_obj1.maximumPower = 100

    # Create the corresponding model that is a NeighborModel
    test_mdl1 = NeighborModel()
    test_mdl1.defaultPower = 10

    test_obj1.model = test_mdl1
    test_mdl1.object = test_obj1

    mtn.neighbors = [test_obj1]

    print('- configuring a test LocalAsset and its LocalAssetModel')
    # Create a test object that is a Local Asset
    test_obj2 = LocalAsset()  # Note that parentheses are manditory where there is complex inheritance!
    test_obj2.maximumPower = 100

    # Create the corresponding model that is a LocalAssetModel
    test_mdl2 = LocalAssetModel()
    test_mdl2.defaultPower = 10

    test_obj2.model = test_mdl2
    test_mdl2.object = test_obj2

    mtn.localAssets = [test_obj2]

    try:
        test_mkt.schedule(mtn)
        print('- method ran without errors')
    except:
        raise ('- method did not run due to errors')

    if len(test_mdl1.scheduledPowers) != 1:
        raise ('- the wrong numbers of scheduled powers were stored for the Neighbor')
    else:
        print('- the right number of scheduled powers were stored for the Neighbor')

    if len(test_mdl2.scheduledPowers) != 1:
        raise ('- the wrong numbers of scheduled powers were stored for the LocalAsset')
    else:
        print('- the right number of scheduled powers were stored for the LocalAsset')

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_sum_vertices():
    print('Running Market.test_sum_vertices()')
    pf = 'pass'

    # Create a test myTransactiveNode object.
    test_node = myTransactiveNode()

    # Create a test Market object.
    test_market = Market()

    # List the test market with the test_node.
    test_node.markets = test_market

    # Create and store a time interval to work with.
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)
    mkt = test_market
    mct = dt
    st = dt
    time_interval = TimeInterval(at, dur, mkt, mct, st)
    test_market.timeIntervals = [time_interval]

    # Create test LocalAsset and LocalAssetModel objects
    test_asset = LocalAsset()
    test_asset_model = LocalAssetModel()

    # Add the test_asset to the test node list.
    test_node.localAssets = [test_asset]

    # Have the test asset and its model cross reference one another.
    test_asset.model = test_asset_model
    test_asset_model.object = test_asset

    # Create and store an active Vertex or two for the test asset
    test_vertex = [
        Vertex(0.2, 0, -110),
        Vertex(0.2, 0, -90)
    ]
    interval_values = [
        IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[0]),
        IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[1])
    ]
    test_asset_model.activeVertices = [interval_values[0], interval_values[1]]  # interval_value(1:2)

    # Create test Neighbor and NeighborModel objects.
    test_neighbor = Neighbor()
    test_neighbor_model = NeighborModel()

    # Add the test neighbor to the test node list.
    test_node.neighbors = [test_neighbor]

    # Have the test neighbor and its model cross reference one another.
    test_neighbor.model = test_neighbor_model
    test_neighbor.model.object = test_neighbor

    # Create and store an active Vertex or two for the test neighbor
    test_vertex.append(Vertex(0.1, 0, 0))
    test_vertex.append(Vertex(0.3, 0, 200))
    interval_values.append(IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[2]))
    interval_values.append(IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[3]))
    test_neighbor_model.activeVertices = [interval_values[2], interval_values[3]]

    ## Case 1
    print('- Case 1: Basic case with interleaved vertices')

    # Run the test.
    try:
        vertices = test_market.sum_vertices(test_node, time_interval)
        print('  - the method ran without errors')
    except:
        pf = 'fail'
        print('  - the method had errors when called and stopped')

    if len(vertices) != 4:
        pf = 'fail'
        print('  - an unexpected number of vertices was returned')
    else:
        print('  - the expected number of vertices was returned')

    powers = [x.power for x in vertices]

    # if any(~ismember(single(powers), single([-110.0000, -10.0000, 10.0000, 110.0000])))
    if len([x for x in powers if round(x,4) not in [-110.0000, -10.0000, 10.0000, 110.0000]]) > 0:
        pf = 'fail'
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex powers were as expected')

    marginal_prices = [round(x.marginalPrice,4) for x in vertices]

    # if any(~ismember(single(marginal_prices), single([0.1000, 0.2000, 0.3000])))
    if len([x for x in marginal_prices if round(x,4) not in [0.1000, 0.2000, 0.3000]]) > 0:
        pf = 'fail'
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex marginal prices were as expected')

    ## CASE 2: NEIGHBOR MODEL TO BE EXCLUDED
    # This case is needed when a demand or supply curve must be created for a
    # transactive Neighbor object. The active vertices of the target Neighbor
    # must be excluded, leaving a residual supply or demand curve against which
    # the Neighbor may plan.
    print('- Case 2: Exclude test Neighbor model')

    # Run the test.
    try:
        # [vertices] = test_market.sum_vertices(test_node, time_interval, test_neighbor_model)
        vertices = test_market.sum_vertices(test_node, time_interval, test_neighbor_model)
        print('  - the method ran without errors')
    except:
        pf = 'fail'
        print('  - the method encountered errors and stopped')

    if len(vertices) != 2:
        pf = 'fail'
        print('  - an unexpected number of vertices was returned')
    else:
        print('  - the expected number of vertices was returned')

    powers = [round(x.power, 4) for x in vertices]

    # if any(~ismember(single(powers), single([-110.0000, -90.0000])))
    if len([x for x in powers if x not in [-110.0000, -90.0000]]) > 0:
        pf = 'fail'
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex powers were as expected')

    marginal_prices = [x.marginalPrice for x in vertices]

    # if any(~ismember(single(marginal_prices), single([0.2000])))
    if len([x for x in marginal_prices if round(x,4) not in [0.2000]]) > 0:
        pf = 'fail'
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex marginal prices were as expected')

    # CASE 3: CONSTANT SHOULD NOT CREATE NEW NET VERTEX
    print('- Case 3: Include a constant vertex. No net vertex should be added')

    # Change the test asset to NOT have any flexibility. A constant should
    # not introduce a net vertex at a constant's marginal price. Marginal
    # price is NOT meaningful for an inelastic device.
    test_asset_model.activeVertices = [interval_values[0]]

    # Run the test.
    try:
        # [vertices] = test_market.sum_vertices(test_node, time_interval)
        vertices = test_market.sum_vertices(test_node, time_interval)
        print('  - the method ran without errors')
    except:
        pf = 'fail'
        print('  - the method encountered errors and stopped')

    #%[180907DJH: THIS TEST IS CORRECTED. THE NEIGHBOR HAS TWO VERTICES. ADDING
    #AN ASSET WITH ONE VERTEX (NO FLEXIBILITY) SHOULD NOT CHANGE THE NUMBER OF
    #ACTIVE VERTICES, SO THE CORRECTED TEST CONFIRMS TWO VERTICES. THE CODE HAS
    #BEEN CORRECTED ACCORDINGLY.]
    if len(vertices) != 2:
        pf = 'fail'
        print('  - an unexpected number of vertices was returned')
    else:
        print('  - the expected number of vertices was returned')

    powers = [x.power for x in vertices]

    # if any(~ismember(single(powers), single([-110.0000, 90])))
    if len([x for x in powers if round(x,4) not in [-110.0000, 90]]) > 0:
        pf = 'fail'
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex powers were as expected')

    marginal_prices = [x.marginalPrice for x in vertices]

    # if any(~ismember(single(marginal_prices), single([0.1000, 0.3000, Inf])))
    if len([x for x in marginal_prices if round(x,4) not in [0.1000, 0.3000, float("inf")]]) > 0:
        pf = 'fail'
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex marginal prices were as expected')

    # CASE 4: More than two vertices at any marginal price
    print('- Case 4: More than two vertices at same marginal price')

    # Move the two active vertices of the test asset to be at the same
    # marginal price as one of the neighbor active vertices.
    test_vertex = [
        Vertex(0.1, 0, -110),
        Vertex(0.1, 0, -90)
    ]
    interval_values = [
        IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[0]),
        IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[1])
    ]
    test_asset_model.activeVertices = [interval_values[0], interval_values[1]]  # interval_value(1:2)

    # Run the test.
    try:
        vertices = test_market.sum_vertices(test_node, time_interval)
        print('  - the method ran without errors')
    except:
        pf = 'fail'
        print('  - the method encountered errors and stopped')

    if len(vertices) != 3:
        pf = 'fail'
        print('  - an unexpected number of vertices was returned')
    else:
        print('  - the expected number of vertices was returned')

    powers = [x.power for x in vertices]

    # if any(~ismember(single(powers), single([-110.0000, -90.0000, 110.0000])))
    if len([x for x in powers if round(x,4) not in [-110.0000, -90.0000, 110.0000]]) > 0:
        pf = 'fail'
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex powers were as expected')

    marginal_prices = [x.marginalPrice for x in vertices]

    # if any(~ismember(single(marginal_prices), single([0.1000, 0.3000])))
    if len([x for x in marginal_prices if round(x,4) not in [0.1000, 0.3000]]) > 0:
        pf = 'fail'
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex marginal prices were as expected')

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_update_costs():
    print('Running Market.test_update_costs()')
    pf = 'test is not complete'

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_update_supply_demand():
    print('Running Market.test_update_supply_demand()')
    pf = 'test is not complete'

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)

def test_events():
    """
    Tests transitions within the generalized market state machine:
    STATE               STATE TRANSITION                            STATE PERSISTENCE
    1. Active           market gets instantiated                    while in an activation lead period
    2. Negotiation      negotiation period starts                   while in a negotiation lead period
    3. MarketLead       negotiation period stops                    while in a market lead period
    4. DeliveryLead     market clears                               while in a delivery lead period
    5. Delivery         delivery starts                             while in any market intervals' delivery period
    6. Reconcile        delivery stops                              until reconciled
    7. Expire           market gets reconciled                      forever thereafter
   """

    print("Running test_events.\n")

    # ******************************************************************************************************************
    print("  CASE 1a: New market should not be instantiated by an existing one prior to its calculated activation time")
    """
    Market timing of a new market is based on the NEXT market clearing time of the existing market.
    market_clearing_time[1] = next_market_clearing_time[0] 
    activation_time[1] = next_market_clearing_time[0] - market_lead_time - negotiation_lead_time - activation_lead_time
    Therefore, Case 1a tests that no new market is created while 
    
                                            now < activation_time[1].
    
    A side condition will be that the existing market should be and remain in its delivery period.
    delivery_start_time[0] = market_clearing_time[0] + delivery_lead_time
    delivery_end_time[0] = market_clearing_time[0] + delivery_lead_time + intervals_to_clear * interval_duration
    
                             delivery_start_time[0] < now < delivery_end_time[0]
    """

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Delivery

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - 0.5 * test_mkt.intervalsToClear * test_mkt.intervalDuration

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]

    # Check required conditions of Case 1a:
    # On the state of the EXISTING market:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    delivery_end_time = delivery_start_time + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_start_time < now < delivery_end_time, "The existing market must be in delivery"

    # On the state of the new market:
    activation_time = test_mkt.nextMarketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                         - test_mkt.activationLeadTime
    assert now < activation_time, "The current time must precede the new activation time"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert 0 < len(test_mtn.markets) < 2, "There should remain exactly one active market"
    assert test_mtn.markets[0] == test_mkt, "The listed market should not have changed"

    print("  Case 1a ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 1b: Existing market should remain in this state if it is within the active state period.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Active

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.activationLeadTime + test_mkt.negotiationLeadTime \
                                  + test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    # Check required conditions before Case 1b:
    activation_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                      - test_mkt.activationLeadTime
    negotiation_start_time = activation_time + test_mkt.activationLeadTime
    assert activation_time < now < negotiation_start_time, "The existing market must be in its active state period"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Active, "The existing market should have remaining in its active state"

    print("  Case 1b ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 1c: A new market object is needed and must be instantiated with its market intervals.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Active

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.activationLeadTime + test_mkt.negotiationLeadTime \
                                  + test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = now + test_mkt.marketLeadTime + test_mkt.negotiationLeadTime \
                                      + 0.5 * test_mkt.activationLeadTime

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    # Check required conditions before Case 1b:
    # While not essential to the test, let's make sure that the existing market does not expire during the test.
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert now < delivery_end_time, "The existing market must be in delivery"

    next_activation_time = test_mkt.nextMarketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                      - test_mkt.activationLeadTime
    assert next_activation_time < now, "It mus be later than the needed market activation time to trigger " \
                                             "instantiation of the new market"



    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 2, "There should be two active markets"
    assert test_mtn.markets[0] == test_mkt, "The existing market should be in position 0"
    assert test_mtn.markets[1].marketName == test_mkt.marketName, \
                                            "The new market name should be the same as that of the existing market"
    assert test_mtn.markets[1].marketState == MarketState.Active, \
        "The new market should have been created and remain in its active state"
    """
    assert len(test_mtn.markets[1].timeIntervals) == test_mkt.intervalsToClear, \
        "The new market did not create the expected number of market intervals"
        """
    # TODO: THIS LAST ASSERT IS NOT WORKING. MODULE CHECK_INTERVALS DOES NOT APPEAR TO WORK YET. THE PROBLEM LIES WITH METHOD CHECK_INTERVALS, NOT HERE.

    print("  Case 1c ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 2a: The existing market should transition from the Active to Negotiation state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Active

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.negotiationLeadTime + test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    negotiation_start_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                      - test_mkt.activationLeadTime + test_mkt.activationLeadTime
    negotiation_end_time = negotiation_start_time + test_mkt.negotiationLeadTime
    assert negotiation_start_time < now < negotiation_end_time, \
        "The existing market must be in its negotiation state period"
    assert test_mkt.marketState == MarketState.Active, "The market must be in its Active state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Negotiation, \
        "The existing market should have transitioned to its negotiation state"


    print("  Case 2a ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 2b: The existing market should remain in its Negotiation state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Negotiation

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.negotiationLeadTime + test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    negotiation_start_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                      - test_mkt.activationLeadTime + test_mkt.activationLeadTime
    negotiation_end_time = negotiation_start_time + test_mkt.negotiationLeadTime
    assert negotiation_start_time < now < negotiation_end_time, \
        "The existing market must be in its negotiation state period"
    assert test_mkt.marketState == MarketState.Negotiation, "The market must be in its Negotiation state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Negotiation, \
        "The existing market should have remained in its negotiation state"

    print("  Case 2b ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 3a: The existing market should transition from the Negotiation to its Market Lead state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Negotiation

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    negotiation_end_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime
    market_clearing_lead_start_time = negotiation_end_time + test_mkt.marketLeadTime
    assert negotiation_end_time < now < market_clearing_lead_start_time, \
        "The existing market must be in its Market Lead state period"
    assert test_mkt.marketState == MarketState.Negotiation, "The market must be in its Negotiation state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.MarketLead, \
        "The existing market should have transitioned to its Market Lead state"

    print("  Case 3a ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 3b: The existing market should remain in its Market Lead state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.MarketLead

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    negotiation_end_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime
    market_clearing_lead_start_time = test_mkt.marketClearingTime
    assert negotiation_end_time < now < market_clearing_lead_start_time, \
        "The existing market must be in its Market Lead state period"
    assert test_mkt.marketState == MarketState.MarketLead, "The market must be in its Market Lead state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.MarketLead, \
        "The existing market should have remained in its Market Lead state"

    print("  Case 3b ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 4a: The existing market should transfer from Market Lead to its Delivery Lead state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.MarketLead

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - 0.5 * test_mkt.deliveryLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    assert test_mkt.marketClearingTime < now < delivery_start_time, \
        "The existing market must be in its Delivery Lead state period"
    assert test_mkt.marketState == MarketState.MarketLead, "The market must be in its Market Lead state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.DeliveryLead, \
        "The existing market should have transitioned to its Delivery Lead state"

    print("  Case 4a ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 4b: The existing market should remain in its Delivery Lead state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.DeliveryLead

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - 0.5 * test_mkt.deliveryLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    assert test_mkt.marketClearingTime < now < delivery_start_time, \
        "The existing market must be in its Delivery Lead state period"
    assert test_mkt.marketState == MarketState.DeliveryLead, "The market must be in its Delivery Lead state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.DeliveryLead, \
        "The existing market should have remained in its Delivery Lead state"

    print("  Case 4b ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 5a: The existing market should transition into its Delivery state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.DeliveryLead

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime  - 0.5 * test_mkt.intervalDuration

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    delivery_end_time = delivery_start_time + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_start_time < now < delivery_end_time, \
        "The existing market must be in its Delivery state period"
    assert test_mkt.marketState == MarketState.DeliveryLead, "The market must be in its Delivery Lead state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Delivery, \
        "The existing market should have remained in its Delivery Lead state"

    print("  Case 5a ran to completion\n")

    # ******************************************************************************************************************
    print("  Case 5b: The existing market should remain in its Delivery state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Delivery

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime  - 0.5 * test_mkt.intervalDuration

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    delivery_end_time = delivery_start_time + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_start_time < now < delivery_end_time, \
        "The existing market must be in its Delivery state period"
    assert test_mkt.marketState == MarketState.Delivery, "The market must be in its Delivery state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Delivery, \
        "The existing market should have remained in its Delivery Lead state"

    print("  Case 5b ran to completion\n")

# ******************************************************************************************************************
    print("  Case 6a: The existing market should transition into its Reconcile state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Delivery

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime \
                                  - test_mkt.intervalsToClear * test_mkt.intervalDuration - timedelta(minutes=1)

    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + 2* test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.reconciled = False
    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_end_time < now, "The existing market must be in its Reconcile state period"
    assert test_mkt.marketState == MarketState.Delivery, "The market must be in its Delivery state"
    assert test_mkt.reconciled is False, "The market must not be reconciled"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Reconcile, \
        "The existing market should have transitioned to its Reconcile state"

    print("  Case 6a ran to completion\n")

# ******************************************************************************************************************
    print("  Case 6b: The existing market should remain in its Reconcile state.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Reconcile

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime \
                                  - test_mkt.intervalsToClear * test_mkt.intervalDuration - timedelta(minutes=1)

    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + 2* test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.reconciled = False
    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_end_time < now, "The existing market must be in its Reconcile state period"
    assert test_mkt.marketState == MarketState.Reconcile, "The market must be in its Reconcile state"
    assert test_mkt.reconciled is False, "The market must not be reconciled"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Reconcile, \
        "The existing market should have transitioned to its Reconcile state"

    print("  Case 6b ran to completion\n")

# ******************************************************************************************************************
    print("  Case 7a: When reconciled, the existing market should transition into its Expired state and terminiate.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Reconcile

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime \
                                  - test_mkt.intervalsToClear * test_mkt.intervalDuration - timedelta(minutes=1)

    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + 2* test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.reconciled = True  # This is the condition that allows the market to expire.
    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_end_time < now, "The existing market must be in its Reconcile state period"
    assert test_mkt.marketState == MarketState.Reconcile, "The market must be in its Reconcile state"
    assert test_mkt.reconciled is True, "The market must be reconciled to allow the transition to Expired"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 0, "The market should have been removed from the agent's list"
    assert test_mkt.marketState == MarketState.Expired, \
        "The existing market should have transitioned to its Expired state"

    print("  Case 7a ran to completion\n")

# ******************************************************************************************************************
    print("  Case 7b: When Expired, the existing market should terminiate.")

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Reconcile

    test_mkt.marketName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime \
                                  - test_mkt.intervalsToClear * test_mkt.intervalDuration - timedelta(minutes=1)

    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + 2* test_mkt.marketClearingInterval

    test_mtn = myTransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.reconciled = True  # This is the condition that allows the market to expire.
    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_end_time < now, "The existing market must be in its Reconcile state period"
    assert test_mkt.marketState == MarketState.Expired, "The market must be in its Reconcile state"
    assert test_mkt.reconciled is True, "The market must be reconciled to allow the transition to Expired"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market object"

    try:
        test_mkt.events(test_mtn)

    except:
        pass

    assert len(test_mtn.markets) == 0, "The market should have been inactivated, removed from the agent's list"
    assert test_mkt.marketState is not, \
        "The existing market should have become terminated"

    print("  Case 7b ran to completion\n")

"""
def test_view_net_curve():
    print('Running Market.test_view_net_curve()')
    pf = 'pass'

    # Establish a test market
    test_mkt = Market()

    # Create and store one TimeInterval
    dt = datetime(2018, 1, 1, 12, 0, 0)
    at = dt
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    st = dt
    ti = [TimeInterval(at, dur, mkt, mct, st)]

    test_mkt.timeIntervals = ti

    ## Test using a Market object
    print('- using a Market object')

    # Create and store three active vertices
    v = [Vertex(0.01, 0, -1), Vertex(0.02, 0, 1), Vertex(0.03, 0, 1)]
    iv = [
        IntervalValue(test_mkt, ti[0], test_mkt, MeasurementType.ActiveVertex, v[2]),
        IntervalValue(test_mkt, ti[0], test_mkt, MeasurementType.ActiveVertex, v[0]),
        IntervalValue(test_mkt, ti[0], test_mkt, MeasurementType.ActiveVertex, v[1])
    ]
    test_mkt.activeVertices = [iv]

    test_mkt.view_net_curve(0)
    print('  - function ran without errors')

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)
    """

"""
def test_view_marginal_prices():
    print('Running Market.test_view_marginal_prices()')
    pf = 'pass'

    # Establish a test market
    test_mkt = Market

    # Create and store three TimeIntervals
    dt = datetime
    at = dt
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt

    ti = []  # TimeInterval.empty

    st = dt
    ti[0] = TimeInterval(at, dur, mkt, mct, st)

    st = st + dur
    ti[1] = TimeInterval(at, dur, mkt, mct, st)

    st = st + dur
    ti[2] = TimeInterval(at, dur, mkt, mct, st)

    test_mkt.timeIntervals = ti

    ## Test using a Market object
    print('- using a Market object')

    iv = []  # IntervalValue.empty
    # Create and store three marginal price values
    iv[0] = IntervalValue(test_mkt, ti[2], test_mkt, MeasurementType.MarginalPrice, 3)
    iv[1] = IntervalValue(test_mkt, ti[0], test_mkt, MeasurementType.MarginalPrice, 1)
    iv[2] = IntervalValue(test_mkt, ti[1], test_mkt, MeasurementType.MarginalPrice, 2)
    test_mkt.marginalPrices = iv

    try:
        test_mkt.view_marginal_prices()
        print('  - function ran without errors')
    except:
        raise ('  - function encountered errors and stopped')

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)
    """


if __name__ == '__main__':
    #test_all()
    test_events()