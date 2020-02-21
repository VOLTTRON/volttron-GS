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


from datetime import date, time
# from dateutil import relativedelta

from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from interval_value import IntervalValue
from transactive_record import TransactiveRecord
from meter_point import MeterPoint
from market import Market
from time_interval import TimeInterval
from neighbor_model import Neighbor
from local_asset_model import LocalAsset
from TransactiveNode import TransactiveNode
from bulk_supplier_dc import BulkSupplier_dc


def test_calculate_reserve_margin():
    # TEST_LAM_CALCULATE_RESERVE_MARGIN() - a LocalAsset ("LAM") class
    # method NOTE: Reserve margins are introduced but not fully integrated into
    # code in early template versions.
    # CASES:
    # 1. uses hard maximum if no active vertices exist
    # 2. vertices exist
    # 2.1 uses maximum vertex power if it is less than hard power constraint
    # 2.2 uses hard constraint if it is less than maximum vertex power
    # 2.3 upper flex power is greater than scheduled power assigns correct
    # positive reserve margin
    # 2.4 upperflex power less than scheduled power assigns zero value to
    # reserve margin.
    print('  Running Neighbor.test_calculate_reserve_margin()')

    # Establish a test market
    test_mkt = Market()

    # Establish test market with an active time interval
    # Modified 1/29/18 due to new TimeInterval constructor
    dt = datetime.now()
    at = dt
    # NOTE: Function Hours() corrects behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    # NOTE: Function Hours() corrects behavior of Matlab hours().
    # st = datetime(date) + Hours(12)  # today at noon
    st = datetime.combine(date.today(), time()) + timedelta(hours=12)

    ti = TimeInterval(at, dur, mkt, mct, st)

    test_mkt.timeIntervals = [ti]

    # Establish a test object that is a LocalAsset with assigned maximum power
    # test_object = Neighbor()

    # Establish test object that is a Neighbor
    test_model = Neighbor()
    test_model.scheduledPowers = [IntervalValue(test_model, ti, test_mkt, MeasurementType.ScheduledPower, 0.0)]
    test_model.maximumPower = 100

    # Allow object and model to cross-reference one another.
    # test_object.model = test_model
    # test_model.object = test_object

    # Run the first test case.
    print('    TEST: Use maximum power')
    try:
        test_model.calculate_reserve_margin(test_mkt)
        print('    The method ran without errors')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert len(test_model.reserveMargins) == 1, '- an unexpected number of results were stored'

    assert test_model.reserveMargins[0].value == 100, '- the method did not use the available maximum power'

    # create some vertices and store them
    interval_value1 = IntervalValue(test_model, ti, test_mkt, MeasurementType.Vertex, Vertex(0, 0, -10))
    interval_value2 = IntervalValue(test_model, ti, test_mkt, MeasurementType.Vertex, Vertex(0, 0, 10))
    test_model.activeVertices = [interval_value1, interval_value2]

    # run test with maximum power greater than maximum vertex
    print('    TEST: Maximum power greater than maximum vertex')
    test_model.maximumPower = 100
    try:
        test_model.calculate_reserve_margin(test_mkt)
        print("    The method ran without errors")
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert test_model.reserveMargins[0].value == 10, '- the method should have used vertex for comparison'

    # run test with maximum power less than maximum vertex
    print('    TEST: Maximum power less than maximum vertex')
    test_model.maximumPower = 5
    try:
        test_model.calculate_reserve_margin(test_mkt)
        print('    Method ran without errors')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert test_model.reserveMargins[0].value == 5, '- method should have used maximum power for comparison'

    # run test with scheduled power greater than maximum vertex
    print('    TEST: scheduled power greater than maximum vertex')
    test_model.scheduledPowers[0].value = 20
    test_model.maximumPower = 500
    try:
        test_model.calculate_reserve_margin(test_mkt)
        print('    The method ran witout errors')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert test_model.reserveMargins[0].value == 0, '- method should have assigned zero for a neg. result'

    # Success.
    print('  test_calculate_reserve_margin() ran to completion.\n')


def test_check_for_convergence():
    print('  Running Neighbor.test_check_for_convergence()')

    one_hour = timedelta(hours=1)

    # Create a test Neighbor object.
    test_model = Neighbor()
    test_model.convergenceThreshold = 0.01
    test_model.converged = True

    # Create a test Market object.
    test_market = Market()

    # Create and store an active TimeInterval object.
    dt = datetime.now()
    time_intervals = TimeInterval(dt, one_hour, test_market, dt, dt)
    test_market.timeIntervals = [time_intervals]

    # TEST 1: No TransactiveRecord messages have been sent.
    print('    Test 1: Property sentSignal is empty')
    try:
        test_model.check_for_convergence(test_market)
        print('    The method ran to completion')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert len(test_model.convergenceFlags) == 1, '  - an unexpected number of convergence flags occurred'
    assert test_model.convergenceFlags[0].value is False, '  - the interval convergence flag should have been false'
    assert test_model.converged is False, '  - the overall convergence should have been false'

    # TEST 2: Compare sent and received signals with identical records
    print('    Test 2: Comparing identical sent and received transactive records')

    test_model.converged = False  # Preset to  ensure test changes status.

    # Create a couple TransactiveRecord objects. NOTE: sent and received records have opposite signs for their powers.
    # These should therefore match and show convergence. The timestamp of the the record for receivedSignal should be
    # made LATER than that for the sent as this is a precondition that must be met.
    tr = [
        TransactiveRecord(time_interval=time_intervals, record=0, marginal_price=0.05, power=100),
        TransactiveRecord(time_interval=time_intervals, record=0, marginal_price=0.05, power=-100)]
    tr[0].timeStamp = datetime.now() + one_hour

    # NOTE: The latter-defined record must be placed in receivedSignal to satisfy a precondition.
    test_model.sentSignal = [tr[0]]
    test_model.receivedSignal = [tr[1]]
    test_model.mySignal = test_model.sentSignal  # This is needed to prevent are_different2() from asserting differences

    try:
        test_model.check_for_convergence(test_market)
        print('    The method ran to completion')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert len(test_model.convergenceFlags) == 1, '  - an unexpected number of interval convergence flags occurred'
    assert test_model.convergenceFlags[0].value is True, '  - the interval convergence flag should have been true'
    assert test_model.converged is True, '  - the overall convergence should have been true'

    # TEST 3: Revise records' scheduled powers to show lack of convergence
    print('    Test 3: Revise powers to destroy convergence between sent and received messages')
    test_model.receivedSignal[0].power = 1.02 * test_model.receivedSignal[0].power

    try:
        test_model.check_for_convergence(test_market)
        print('    The method ran to completion')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert len(test_model.convergenceFlags) == 1, '  - an unexpected number of interval convergence flags occurred'
    assert test_model.convergenceFlags[0].value is False, '  - the interval convergence flag should have been false'
    assert test_model.converged is False, '  - the overall convergence should have been false'

    # TEST 4: Sent and received signals differ, no signal received since last send
    print('    Test 4: No received signal since last send')
    dt = datetime.now()
    test_model.sentSignal[0].timeStamp = format_ts(dt)  # Must be >5 minutes ago
    test_model.receivedSignal[0].timeStamp = format_ts(dt)

    try:
        test_model.check_for_convergence(test_market)
        print('    The method ran to completion')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert len(test_model.convergenceFlags) == 1, '  - an unexpected number of interval convergence flags occurred'
    assert test_model.convergenceFlags[0].value is True, '  - the interval convergence flag should have been true'
    assert test_model.converged is True, '  - the overall convergence should have been true'

    # TEST 5: Compare identical mySignal and sentSignal records
    print('    Test 5: Identical mySignal and sentSignal contents')

    #   Create prepared mySignal message that is exactly the same as the sent
    #   message.
    test_model.mySignal = [tr[0]]
    test_model.sentSignal = [tr[0]]

    #   Ensure that the sent signal was sent much more than 5 minutes ago
    test_model.sentSignal[0].timeStamp = format_ts(dt - one_hour)

    #   Ensure that a signal has NOT been received since the last one was sent.
    #   This intentionally violates a precondition so that the method under
    #   test will not compare the sent and received messages.
    test_model.receivedSignal[0].timeStamp = format_ts(dt - 2 * one_hour)

    try:
        test_model.check_for_convergence(test_market)
        print('    The method ran to completion')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert len(test_model.convergenceFlags) == 1, '  - an unexpected number of interval convergence flags occurred'
    assert test_model.convergenceFlags[0].value is True, '  - the interval convergence flag should have been true'
    assert test_model.converged is True, '  - the overall convergence should have been true'

    # TEST 6: Compare multiple matched mySignal and testSignal records
    print('    Test 6: Compare multiple matched mySignal and testSignal records')

    # Create a couple new TransactiveRecord objects.
    tr.append(TransactiveRecord(time_interval=time_intervals, record=1, marginal_price=0.049, power=90))
    tr[2].timeStamp = test_model.sentSignal[0].timeStamp

    tr.append(TransactiveRecord(time_interval=time_intervals, record=2, marginal_price=0.051, power=110))
    tr[3].timeStamp = test_model.sentSignal[0].timeStamp

    # Append the mySignal and sentSignal records. The sets should still remain
    # identical, meaning that the system has not changed and remains converged.
    test_model.mySignal = [tr[0], tr[2], tr[3]]
    test_model.sentSignal = [tr[0], tr[2], tr[3]]

    try:
        test_model.check_for_convergence(test_market)
        print('    The method ran to completion')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert len(test_model.convergenceFlags) == 1, '  - an unexpected number of interval convergence flags occurred'
    assert test_model.convergenceFlags[0].value is True, '  - the interval convergence flag should have been true'
    assert test_model.converged is True, '  - the overall convergence should have been true'

    # TEST 7: A Vertex differs significantly between mySignal and sentSignal
    print('    Test 7: mySignal and sentSignal differ significantly, multiple points.')

    # Change mySignal to be significantly different from sentSignal.
    #   test_model.mySignal[0].

    tr.append(TransactiveRecord(time_interval=time_intervals, record=1, marginal_price=0.049, power=85))
    test_model.mySignal = [tr[0], tr[4], tr[3]]

    try:
        test_model.check_for_convergence(test_market)
        print('    The method ran to completion')
    except RuntimeWarning:
        print('    ERRORS ENCOUNTERED')

    assert len(test_model.convergenceFlags) == 1, '  - an unexpected number of interval convergence flags occurred'
    assert test_model.convergenceFlags[0].value is False, '  - the interval convergence flag should have been false'
    assert test_model.converged is False, '  - the overall convergence should have been false'

    #   Success.
    print("  test_check_for_convergence() ran to completion.\n")


def test_marginal_price_from_vertices():
    # TEST_MARGINAL_PRICE_FROM_VERTICES() - test method
    # marginal_price_from_vertices().
    print('Running Neighbor.test_marginal_price_from_vertices()')

    # CASES:
    # - power less than leftmost vertex
    # - power greater than rightmost vertex
    # - power between two vertices

    # Create a test Neighbor object.
    test_obj = Neighbor()

    # Create and store two test Vertex objects. Misorder to test ordering.
    test_vertice1 = Vertex(0.2, 0, 100)
    test_vertice2 = Vertex(0.1, 0, -100)
    test_vertices = [test_vertice1, test_vertice2]

    # Test 1: Power less than leftmost vertex.
    print('- Test 1: power less than leftmost Vertex')
    power = -150

    try:
        marginal_price = test_obj.marginal_price_from_vertices(power, test_vertices)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')
        marginal_price = []

    assert marginal_price == test_vertices[1].marginalPrice, '  - the method returned an unexpected marginal price'

    # Test 2: Power greater than the rightmost Vertex.
    print('- Test 2: power greater than the rightmost Vertex')
    power = 150

    try:
        marginal_price = test_obj.marginal_price_from_vertices(power, test_vertices)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert marginal_price == test_vertices[0].marginalPrice, '  - the method returned an unexpected marginal price'

    # Test 3: Power between vertices.
    print('- Test 3: power is between vertices')
    power = 0

    try:
        marginal_price = test_obj.marginal_price_from_vertices(power, test_vertices)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert abs(marginal_price - 0.15) <= 0.0001, '  - the method returned an unexpected marginal price'

    # Success.
    print('test_marginal_price_from_vertices() ran to completion.\n')


def test_prep_transactive_signal():
    print('Running Neighbor.test_prep_transactive_signal()')

    # Create a test model.
    test_model = Neighbor()

    # Create a test market object.
    test_market = Market()

    # Create a test LocalAsset object.
    test_asset_model = LocalAsset()

    # Create a test TransactiveNode object and its references to its objects and models.
    test_myTransactiveNode = TransactiveNode()
    test_myTransactiveNode.neighbors = [test_model]
    test_myTransactiveNode.localAssets = [test_asset_model]
    test_myTransactiveNode.markets = [test_market]

    # Create and store a TimeInterval object
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)  # Hours(1)
    mkt = test_market
    mct = dt
    st = dt
    time_interval = TimeInterval(at, dur, mkt, mct, st)
    test_market.timeIntervals = [time_interval]

    # Create some active vertices and their IntervalValue objects ready to
    # choose from for the various tests.
    vertice1 = Vertex(0.1, 0, -100)
    vertice2 = Vertex(0.2, 0, -37.5)
    vertice3 = Vertex(0.3, 0, 0)
    vertice4 = Vertex(0.4, 0, 25)
    vertice5 = Vertex(0.5, 0, 100)
    interval_values = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.TestVertex, vertice1),
        IntervalValue(test_model, time_interval, test_market, MeasurementType.TestVertex, vertice2),
        IntervalValue(test_model, time_interval, test_market, MeasurementType.TestVertex, vertice3),
        IntervalValue(test_model, time_interval, test_market, MeasurementType.TestVertex, vertice4),
        IntervalValue(test_model, time_interval, test_market, MeasurementType.TestVertex, vertice5)
    ]

    # TEST 1
    print('- Test 1: Neighbor is NOT transactive')
    test_model.transactive = False

    try:
        test_model.prep_transactive_signal(test_market, test_myTransactiveNode)
        print('  - The method warned and returned, as expected')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    # TEST 2
    print('- Test 2: The trans. Neighbor is offered no flexibility')

    # Configure the test.
    test_model.transactive = True
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 200)]

    test_asset_model.activeVertices = [interval_values[2]]

    try:
        test_model.prep_transactive_signal(test_market, test_myTransactiveNode)
        print('  - the method ran to completion without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.mySignal) == 1, '  - the wrong number of transactive records were stored'
    assert test_model.mySignal[0].power == -200 and test_model.mySignal[0].marginalPrice == float("inf"), \
        '  - the transactive record values were not as expected'

    # TEST 3
    print('- Test 3: The trans. Neighbor imports from myTransactiveNode')

    # Configure the test.
    test_model.transactive = True
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, -50)]
    test_model.maximumPower = -10
    test_model.minimumPower = -75

    test_asset_model.activeVertices = [interval_values[2], interval_values[4]]

    try:
        test_model.prep_transactive_signal(test_market, test_myTransactiveNode)
        print('  - the method ran to completion without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.mySignal) == 3, '  - the wrong number of transactive records were stored'

    non_members = [x for x in test_model.mySignal if x.power not in [10, 50, 75]]
    assert len(non_members) == 0, '  - the record power values were not as expected'

    cond1 = [abs(x.marginalPrice - 0.3200) < 0.0001 for x in test_model.mySignal]
    cond2 = [abs(x.marginalPrice - 0.4000) < 0.0001 for x in test_model.mySignal]
    cond3 = [abs(x.marginalPrice - 0.4500) < 0.0001 for x in test_model.mySignal]
    assert any(cond1) and any(cond2) and any(cond3), '  - the marginal price values were not as expected'

    # TEST 4
    print('- Test 4: The trans. Neighbor exports to TransactiveNode')

    # Configure the test.
    test_model.transactive = True
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 50)]
    test_model.maximumPower = 75
    test_model.minimumPower = 10

    test_asset_model.activeVertices = [interval_values[0], interval_values[2]]

    try:
        test_model.prep_transactive_signal(test_market, test_myTransactiveNode)
        print('  - the method ran to completion without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.mySignal) == 3, '  - the wrong number of transactive records were stored'

    non_members = [x for x in test_model.mySignal if x.power not in [-10, -50, -75]]
    assert len(non_members) == 0, '  - the record power values were not as expected'

    cond1 = [abs(x.marginalPrice - 0.1500) < 0.0001 for x in test_model.mySignal]
    cond2 = [abs(x.marginalPrice - 0.2000) < 0.0001 for x in test_model.mySignal]
    cond3 = [abs(x.marginalPrice - 0.2800) < 0.0001 for x in test_model.mySignal]
    assert any(cond1) and any(cond2) and any(cond3), '  - the marginal price values were not as expected'

    # TEST 5
    print('- Test 5: There is an extra Vertex in the range')

    # Configure the test.
    test_model.transactive = True
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 50)]
    test_model.maximumPower = 75
    test_model.minimumPower = 25
    test_asset_model.activeVertices = [interval_values[0],
                                       interval_values[1],  # an extra vertex in active flex range
                                       interval_values[2]]

    try:
        test_model.prep_transactive_signal(test_market, test_myTransactiveNode)
        print('  - the method ran to completion without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.mySignal) == 4, '  - the wrong number of transactive records were stored'

    non_members = [x for x in test_model.mySignal if x.power not in [-25, -50, -75, -37.5]]
    assert len(non_members) == 0, '  - the record power values were not as expected'

    cond1 = [abs(x.marginalPrice - 0.1800) < 0.0001 for x in test_model.mySignal]
    cond2 = [abs(x.marginalPrice - 0.1400) < 0.0001 for x in test_model.mySignal]
    cond3 = [abs(x.marginalPrice - 0.2333) < 0.0001 for x in test_model.mySignal]
    cond4 = [abs(x.marginalPrice - 0.2000) < 0.0001 for x in test_model.mySignal]
    assert any(cond1) and any(cond2) and any(cond3) and any(cond4), '  - the marginal price values were not as expected'

    # Success.
    print('test_prep_transactive_signal() ran to completion.\n')


def test_receive_transactive_signal():
    # 191212DJH: The Python code is found to NOT presume a flat text file as designed. Instead, a parameter "curves" is
    # expected upon this call. It would appear that this is now a call to the Neighbor object from another agent or
    # some Volttron element. Ask Hung how this works, since
    # (1) Another agent would not necessarily be able to call this agent's neighbor model, and
    # (2) The assumption might make the method too integrated with Volttron.
    # This test is not meaningful outside of the Volttron environment and should be skipped.
    print('Running Neighbor.test_receive_transactive_signal()')

    # Create a test Neighbor object.
    test_model = Neighbor()

    # Create a test Neighbor object.
    test_model.name = 'TN_abcdefghijklmn'

    # Get the test object and model to cross-reference one another.
    # test_object.model = test_model
    # test_model.object = test_object

    # Create a test market object.
    test_market = Market()

    # Create a test TransactiveNode object.
    test_myTransactiveNode = TransactiveNode()
    test_myTransactiveNode.name = 'mTN_abcd'

    # TEST 1
    print('- Test 1: Neighbor is NOT transactive')
    test_model.transactive = False

    try:
        test_model.receive_transactive_signal(test_myTransactiveNode)
        print('  - The method warned and returned, as expected')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    # Test 2
    print('- Test 2: Read a csv file into received transactive records')

    # Configure for the test.
    test_model.transactive = True

    # Create a test time interval
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)  # Hours(1)
    mkt = test_market
    mct = dt
    st = dt
    time_interval = TimeInterval(at, dur, mkt, mct, st)

    # Create a couple test transactive records.
    test_record1 = TransactiveRecord(time_interval=time_interval, record=0, marginal_price=0.1, power=0)
    test_record2 = TransactiveRecord(time_interval=time_interval, record=1, marginal_price=0.2, power=100)

    test_model.mySignal = [test_record1, test_record2]

    test_model.send_transactive_signal(test_myTransactiveNode)
    print('  - this test depends on method send_transactive_signal() to create a file')

    # Clear the mySignal property that will be used to receive the records.
    test_model.receivedSignal = []

    # A trick is needed because the filenames rely on source and target node names, which are swapped in the reading
    # and sending methods. Exchange the names of the test object and test the TransactiveNode.
    name_holder = test_myTransactiveNode.name
    test_myTransactiveNode.name = test_model.name
    test_model.name = name_holder

    try:
        test_model.receive_transactive_signal(test_myTransactiveNode)
        print('  - the receive method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.receivedSignal) == 2, '  - an unexpected, or no, record count was stored'

    # Success.
    print('test_receive_transactive_signal() ran to completion.\n')


def test_schedule_engagement():
    print('Running Neighbor.test_schedule_engagement()')

    test_obj = Neighbor()

    try:
        test_obj.schedule_engagement()
        print('- method ran to completion')
    except RuntimeWarning:
        print('- ERRORS ENCOUNTERED')

    assert test_obj == test_obj, '- the Neighbor was unexpected altered'

    # Success.
    print('test_schedule_engagement() ran to completion.\n')


def test_schedule_power():
    # TEST_SCHEDULE_POWER() - tests a Neighbor method called schedule_power().
    print('Running Neighbor.test_schedule_power()')

    # Create a test Neighbor object.
    test_model = Neighbor()
    # test_model.defaultPower = 99

    # Create a test Market object.
    test_market = Market()

    # Create and store an active TimeInterval object.
    dt = datetime.now()  # datetime that may be used for all datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    # Create and store a marginal price IntervalValue object.
    test_market.marginalPrices = [
        IntervalValue(test_market, time_interval, test_market, MeasurementType.MarginalPrice, 0.1)]

    # Create a store a simple active Vertex for the test model.
    test_vertex = Vertex(0.1, 0, 100)
    test_interval_value = IntervalValue(test_model, time_interval, test_market,
                                        MeasurementType.ActiveVertex, test_vertex)
    test_model.activeVertices = [test_interval_value]

    # TEST 1
    print('- Test 1: scheduled power does not exist yet')

    try:
        test_model.schedule_power(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.scheduledPowers) == 1, '  - an unexpected number of scheduled powers is created'

    scheduled_power = test_model.scheduledPowers[0].value
    assert scheduled_power == 100, '  - the scheduled power value was not that expected'

    # TEST 2
    print('- Test 2: scheduled power value exists to be reassigned')

    # Configure for test by using a different active vertex.
    test_vertex.power = 50
    test_model.activeVertices[0].value = test_vertex

    try:
        test_model.schedule_power(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.scheduledPowers) == 1, '  - an unexpected number of scheduled powers is found'

    scheduled_power = test_model.scheduledPowers[0].value
    assert scheduled_power == 50, '  - the scheduled power value was not that expected'

    # Success.
    print('test_schedule_power() ran to completion.\n')


def test_send_transactive_signal():
    # 191212DJH: This method under test has become fully integrated with the Volttron environment.
    # This test is not meaningful outside of the Volttron environment and should be skipped.
    import os

    print('Running Neighbor.test_send_transactive_signal()')
    pf = 'pass'

    # Create a test Neighbor object.
    test_model = Neighbor()
    test_model.name = 'NM_abcdefghijkl'

    # Create a test market object.
    test_market = Market()

    # Create a test TransactiveNode object.
    test_myTransactiveNode = TransactiveNode()
    test_myTransactiveNode.name = 'mTN_abcd'

    # TEST 1
    print('- Test 1: Neighbor is NOT transactive')
    test_model.transactive = False

    test_model.send_transactive_signal(test_myTransactiveNode)
    print('  - The method warned and returned, as expected')

    # Test 2
    print('- Test 2: Write transactive records into a csv file')

    # Configure for the test.
    test_model.transactive = True

    # Create a test time interval
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)
    mkt = test_market
    mct = dt
    st = dt
    time_interval = TimeInterval(at, dur, mkt, mct, st)

    # Create a couple test transactive records.
    test_record1 = TransactiveRecord(time_interval=time_interval, record=0, marginal_price=0.1, power=0)
    test_record2 = TransactiveRecord(time_interval=time_interval, record=1, marginal_price=0.2, power=100)

    test_model.mySignal = [test_record1, test_record2]

    test_model.send_transactive_signal(test_myTransactiveNode)
    print('  - the method ran to completion without errors')

    expected_filename = 'mTN_a-TN_ab.txt'

    # if exist(expected_filename, 'file') != 2:
    if not os.path.isfile(expected_filename):
        pf = 'fail'
        print('  - the expected output file does not exist')
    else:
        print('  - the expected output file exists')

    # expected_data = csvread(expected_filename, 1, 3, [1, 3, 2, 4])

    # if expected_data !=[0.1000, 0; 0.2000, 100]:
    #    pf = 'fail'
    #    print('  - the csv file contents were not as expected')
    # else:
    #    print('  - the csv file contents were as expected')
    # TEST 3: Check that the saved sent signal is the same as that calculated.
    print('- Test 3: Was the sent signal saved properly?')

    if test_model.mySignal != test_model.sentSignal:
        pf = 'fail'
        print('  - the sent signal does not match the calculated one')
    else:
        print('  - the sent signal matches the calculated one')

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)

    # Close and delete the file.
    # fclose('all')
    # delete(expected_filename)


def test_update_dc_threshold():
    print('Running Neighbor.test_update_dc_threshold()')
    dt = datetime.now()  # Keep this variable as a datetime!

    # Basic configuration for tests:
    # Create a test object and initialize demand-related properties
    test_obj = BulkSupplier_dc()
    test_obj.demandMonth = dt.month
    test_obj.demandThreshold = 1000

    # Create a test market
    test_mkt = Market()

    # Create and store two time intervals
    at = dt
    dur = timedelta(hours=1)  # Hours(1)
    mkt = test_mkt
    mct = dt

    st = dt
    ti1 = TimeInterval(at, dur, mkt, mct, st)

    st = st + dur
    ti2 = TimeInterval(at, dur, mkt, mct, st)

    ti = [ti1, ti2]
    test_mkt.timeIntervals = ti

    # Test case when there is no MeterPoint object
    test_obj.demandThreshold = 1000
    test_obj.demandMonth = dt.month
    test_obj.meterPoints = []  # MeterPoint.empty

    # Create and store a couple scheduled powers
    iv1 = IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900)
    iv2 = IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    test_obj.scheduledPowers = [iv1, iv2]

    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors')
    except RuntimeWarning:
        print('- ERRORS ENCOUNTERED')

    assert test_obj.demandThreshold == 1000, '- the method inferred the wrong demand threshold value'

    iv1 = IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 1100)
    iv2 = IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    test_obj.scheduledPowers = [iv1, iv2]

    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors when there is no meter')
    except RuntimeWarning:
        print('- ERRORS ENCOUNTERED')

    assert test_obj.demandThreshold == 1100, '- the method did not update the inferred demand threshold value'

    # Test with an appropriate MeterPoint meter
    # Create and store a MeterPoint test object
    test_mtr = MeterPoint()
    test_mtr.measurementType = MeasurementType.AverageDemandkW  # 'average_demand_kW'
    test_mtr.currentMeasurement = 900
    test_obj.meterPoints = [test_mtr]

    # Reconfigure the test object for this test:
    iv1 = IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900)
    iv2 = IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    test_obj.scheduledPowers = [iv1, iv2]

    test_obj.demandThreshold = 1000
    test_obj.demandMonth = dt.month

    # Run the test. Confirm it runs.
    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors when there is a meter')
    except RuntimeWarning:
        print('- ERRORS ENCOUNTERED')

    # Check that the old threshold is correctly retained.
    assert test_obj.demandThreshold == 1000, \
        '- the method failed to keep the correct demand threshold value when there is a meter'

    # Reconfigure the test object with a lower current threshold
    iv1 = IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900)
    iv2 = IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    test_obj.scheduledPowers = [iv1, iv2]
    test_obj.demandThreshold = 800

    # Run the test.
    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors with lower current threshold')
    except RuntimeWarning:
        print('- ERRORS ENCOUNTERED')

    # Check that a new, higher demand threshold was set.
    assert test_obj.demandThreshold == 900, \
        '- the method failed to update the demand threshold value when there is a meter'

    # Test rollover to new month
    # Configure the test object
    # test_obj.demandMonth = month(datetime - days(31))  # prior month
    last_month = dt.month - 1
    test_obj.demandMonth = last_month  # (dt - timedelta(days=31)).month  # prior month
    test_obj.demandThreshold = 1000
    test_obj.scheduledPowers[0].value = 900
    test_obj.scheduledPowers[1].value = 900
    # test_obj.meterPoints = MeterPoint.empty
    test_obj.meterPoints = []  # MeterPoint.empty
    test_obj.demandThresholdCoef = 0.8

    # Run the test
    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors upon rollover to new month')
    except RuntimeWarning:
        print('- ERRORS ENCOUNTERED')

    # See if the demand threshold was reset at the new month.
    assert test_obj.demandThreshold == test_obj.demandThresholdCoef * 1000, \
        '- the method did not reduce the threshold properly in a new month'

    # Success
    print('test_update_dc_threshold() ran to completion.\n')


def test_update_dual_costs():
    print('Running Neighbor.test_update_dual_costs()')

    # Create a test Market object.
    test_market = Market()

    # Create and store a TimeInterval object.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    # Create and store a marginal price IntervalValue object.
    test_market.marginalPrices = [
        IntervalValue(test_market, time_interval, test_market, MeasurementType.MarginalPrice, 0.1)]

    # Create a test Neighbor object.
    test_model = Neighbor()

    # Create and store a scheduled power IntervalValue in the active time interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 100)]

    # Create and store a production cost IntervalValue object in the active time interval.
    test_model.productionCosts = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ProductionCost, 1000)]

    # TEST 1
    print('- Test 1: First calculation of a dual cost')

    try:
        test_model.update_dual_costs(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.dualCosts) == 1, '  - the wrong number of dual cost values was created'

    dual_cost = test_model.dualCosts[0].value
    assert dual_cost == (1000 - 100 * 0.1), '  - an unexpected dual cost value was found'

    # TEST 2
    print('- Test 2: Reassignment of an existing dual cost')

    # Configure the test by modifying the marginal price value.
    test_market.marginalPrices[0].value = 0.2

    try:
        test_model.update_dual_costs(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.dualCosts) == 1, '  - the wrong number of dual cost values was created'

    dual_cost = test_model.dualCosts[0].value
    assert dual_cost == (1000 - 100 * 0.2), '  - an unexpected dual cost value was found'

    # Success.
    print('test_update_dual_costs() ran to completion.\n')


def test_update_production_costs():
    print('Running Neighbor.test_update_production_costs()')

    # Create a test Market object.
    test_market = Market()

    # Create and store a TimeInterval object.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    # Create a test Neighbor object.
    test_model = Neighbor()

    # Create and store a scheduled power IntervalValue in the active time
    # interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 50)]

    # Create and store some active vertices IntervalValue objects in the
    # active time interval.
    vertex1 = Vertex(0.1, 1000, 0)
    vertex2 = Vertex(0.2, 1015, 100)
    test_model.activeVertices = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ActiveVertex, vertex1),
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ActiveVertex, vertex2)
    ]

    # TEST 1
    print('- Test 1: First calculation of a production cost')

    try:
        test_model.update_production_costs(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.productionCosts) == 1, '  - the wrong number of production costs was created'

    production_cost = test_model.productionCosts[0].value
    assert production_cost == 1007.5, '  - an unexpected production cost value was found'

    # TEST 2
    print('- Test 2: Reassignment of an existing production cost')

    # Configure the test by modifying the scheduled power value.
    test_model.scheduledPowers[0].value = 150

    try:
        test_model.update_production_costs(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.productionCosts) == 1, '  - the wrong number of productions was created'

    production_cost = test_model.productionCosts[0].value
    assert production_cost == 1015, '  - an unexpected dual cost value was found'

    # Success.
    print('test_update_production_costs() ran to completion.\n')


def test_update_vertices():
    print('Running Neighbor.test_update_vertices()')

    # Create a test Market object.
    test_market = Market()

    # Create and store a TimeInterval object.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    # Create a test Neighbor object.
    test_model = Neighbor()

    # Create and store a scheduled power IntervalValue in the active time interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 50)]

    # Create a Neighbor object and its maximum and minimum powers.
    # test_object = Neighbor()
    test_model.maximumPower = 200
    test_model.minimumPower = 0
    test_model.lossFactor = 0  # eliminate losses from the calcs for now.

    # TEST 1
    print('- Test 1: No default vertex has been defined for the Neighbor')

    test_model.defaultVertices = []

    try:
        test_model.update_vertices(test_market)
        print('  - the method warned and returned, as designed.')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    # TEST 2
    print('- Test 2: The Neighbor is not transactive')

    # Create the default Vertex object.
    test_model.defaultVertices = [Vertex(.1, 0, 100)]
    test_model.transactive = False

    try:
        test_model.update_vertices(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.activeVertices) == 1, '  - there is an unexpected number of active vertices'

    vertex = test_model.activeVertices[0].value
    assert vertex.power == 100 and vertex.marginalPrice == 0.1, '  - the vertex values are not as expected'

    # TEST 3
    print('- Test 3: The Neighbor is transactive, but transactive records are not available')
    test_model.transactive = True
    test_model.defaultVertices = [Vertex(.2, 0, 200)]  # Changed
    test_model.activeVertices = []

    try:
        test_model.update_vertices(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.activeVertices) == 1, '  - there is an unexpected number of active vertices'

    vertex = test_model.activeVertices[0].value
    assert vertex.power == 200 and vertex.marginalPrice == 0.2, '  - the vertex values are not as expected'

    # TEST 4
    print('- Test 4: The Neighbor is transactive, and transactive records are available to use')
    test_model.transactive = True
    test_model.activeVertices = []

    # Create and store some received transactive records
    transactive_record1 = TransactiveRecord(time_interval=time_interval, record=1, marginal_price=0.15, power=0)
    transactive_record2 = TransactiveRecord(time_interval=time_interval, record=2, marginal_price=0.25, power=100)
    transactive_record3 = TransactiveRecord(time_interval=time_interval, record=0, marginal_price=0.2, power=50)
    test_model.receivedSignal = [transactive_record1, transactive_record2, transactive_record3]

    test_model.demandThreshold = 500

    try:
        test_model.update_vertices(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.activeVertices) == 2, '  - there is an unexpected number of active vertices'

    # vertex = [test_model.activeVertices(:).value]
    # vertex_power = [vertex.power]
    # vertex_marginal_price = [vertex.marginalPrice]
    vertex_power = [x.value.power for x in test_model.activeVertices]
    vertex_marginal_price = [x.value.marginalPrice for x in test_model.activeVertices]
    # if any(~ismember([vertex_power], [0, 100]))
    #    or any(~ismember([vertex_marginal_price], [0.1500, 0.2500]))
    non_members1 = [x for x in vertex_power if x not in [0, 100]]
    non_members2 = [x for x in vertex_marginal_price if x not in [0.1500, 0.2500]]
    assert len(non_members1) == 0 and len(non_members2) == 0, '  - the vertex values are not as expected'

    # TEST 5
    print('- Test 5: The Neighbor is transactive with transactive records, and demand charges are in play')
    test_model.transactive = True
    test_model.activeVertices = []

    # Create and store some received transactive records
    transactive_record1 = TransactiveRecord(time_interval=time_interval, record=1, marginal_price=0.15, power=0)
    transactive_record2 = TransactiveRecord(time_interval=time_interval, record=2, marginal_price=0.25, power=100)
    transactive_record3 = TransactiveRecord(time_interval=time_interval, record=0, marginal_price=0.2, power=50)
    test_model.receivedSignal = [transactive_record1, transactive_record2, transactive_record3]

    # The demand threshold is being moved into active vertex range.
    test_model.demandThreshold = 80  #

    try:
        test_model.update_vertices(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_model.activeVertices) == 4, '  - there is an unexpected number of active vertices'

    # vertex = [test_model.activeVertices(:).value]
    # vertex_power = [vertex.power]
    # vertex_marginal_price = [vertex.marginalPrice]
    vertex_power = [x.value.power for x in test_model.activeVertices]
    vertex_marginal_price = [round(x.value.marginalPrice, 4) for x in test_model.activeVertices]

    # if any(~ismember([vertex_power], [0, 80, 100]))
    #    or any(~ismember(single(vertex_marginal_price), single([0.1500, 0.2300, 10.2500, 10.2300])))
    non_members1 = [x for x in vertex_power if x not in [0, 80, 100]]
    non_members2 = [x for x in vertex_marginal_price if x not in [0.1500, 0.2300]]
    assert len(non_members1) == 0 and len(non_members2) == 2, '  - the vertex values are not as expected'

    # Success.
    print('test_update_vertices() ran to completion.\n')


if __name__ == '__main__':
    print('Running tests in testneighbor.py\n')
    test_check_for_convergence()
    test_calculate_reserve_margin()
    test_marginal_price_from_vertices()
    test_prep_transactive_signal()
    # The following test has been modified for Volttron and cannot be tested.
    # test_receive_transactive_signal()
    test_schedule_engagement()
    test_schedule_power()
    # The following test has been modified for Volttron and cannot be tested.
    # test_send_transactive_signal()
    test_update_dc_threshold()
    test_update_dual_costs()
    test_update_production_costs()
    test_update_vertices()
    print('Tests in testneighbor.py ran to completion.\n')
