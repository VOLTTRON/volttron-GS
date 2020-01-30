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


# from datetime import datetime, timedelta, date, time
# from dateutil import relativedelta

# from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from interval_value import IntervalValue
# from transactive_record import TransactiveRecord
from meter_point import MeterPoint
from market import Market
from time_interval import TimeInterval
# from neighbor_model import Neighbor
# from local_asset_model import LocalAsset
# from TransactiveNode import TransactiveNode
from bulk_supplier_dc import BulkSupplier_dc
# from const import *


def test_update_dc_threshold():
    print('Running BulkSupplier_dc.test_update_dc_threshold()')

    # Basic configuration for tests:
    # Create a test object and initialize demand-related properties
    test_obj = BulkSupplier_dc()
    test_obj.demandMonth = datetime.now().month  # month(datetime)
    test_obj.demandThreshold = 1000

    # Create a test market
    test_mkt = Market()

    # Create and store two time intervals
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)  # Hours(1)
    mkt = test_mkt
    mct = dt
    st = dt
    ti = [TimeInterval(at, dur, mkt, mct, st)]
    st = st + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))
    test_mkt.timeIntervals = ti

    #  Test case when there is no MeterPoint object
    test_obj.demandThreshold = 1000
    test_obj.demandMonth = datetime.now().month  # month(datetime)
    test_obj.meterPoints = []  # MeterPoint.empty

    # Create and store a couple scheduled powers
    # iv(1) = IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900)
    # iv(2) = IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    iv = [
        IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900),
        IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    ]
    test_obj.scheduledPowers = iv

    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors')
    except RuntimeWarning:
        print('- the method encountered errors when called')

    assert test_obj.demandThreshold == 1000, '- the method inferred the wrong demand threshold value'

    iv = [
        IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 1100),
        IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    ]
    test_obj.scheduledPowers = iv

    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors when there is no meter')
    except RuntimeWarning:
        print('- the method encountered errors when there is no meter')

    assert test_obj.demandThreshold == 1100, '- the method did not update the inferred demand threshold value'

    # Test with an appropriate MeterPoint meter
    # Create and store a MeterPoint test object
    test_mtr = MeterPoint()
    test_mtr.measurementType = MeasurementType.AverageDemandkW
    test_mtr.currentMeasurement = 900
    test_obj.meterPoints = [test_mtr]

    # Reconfigure the test object for this test:
    iv = [
        IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900),
        IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    ]
    test_obj.scheduledPowers = iv

    test_obj.demandThreshold = 1000
    test_obj.demandMonth = datetime.now().month

    # Run the test. Confirm it runs.
    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors when there is a meter')
    except RuntimeWarning:
        print('- the method encountered errors when there is a meter')

    # Check that the old threshold is correctly retained.
    assert test_obj.demandThreshold == 1000, \
                            '- the method failed to keep the correct demand threshold value when there is a meter'

    # Reconfigure the test object with a lower current threshold
    iv = [
        IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900),
        IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)]
    test_obj.scheduledPowers = iv
    test_obj.demandThreshold = 800

    # Run the test.
    test_obj.update_dc_threshold(test_mkt)

    # Check that a new, higher demand threshold was set.
    assert test_obj.demandThreshold == 900, \
                                    '- the method failed to update the demand threshold value when there is a meter'

    # Test rollover to new month
    # Configure the test object
    last_month = dt.month - 1
    if last_month == 0:
        last_month = 12
    test_obj.demandMonth = last_month  # month(datetime - days(31))  # prior month
    test_obj.demandThreshold = 1000
    test_obj.scheduledPowers[0].value = 900
    test_obj.scheduledPowers[1].value = 900
    test_obj.meterPoints = []  # MeterPoint.empty
    test_obj.demandThresholdCoef = 0.8

    # Run the test
    try:
        test_obj.update_dc_threshold(test_mkt)
        print('  - The method ran without errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    # See if the demand threshold was reset at the new month.
    assert test_obj.demandThreshold == test_obj.demandThresholdCoef * 1000, \
        '- the method did not reduce the threshold properly in a new month'

    # Success
    print('test_update_dc_threshold() ran to completion.\n')


def test_update_vertices():
    print('Running BulkSupplier_dc.test_update_vertices()')
    print('  This test is not completed yet')

    # Success
    print('test_update_vertices() ran to completion.\n')


if __name__ == '__main__':
    print('Running tests in testbulksupplierdc.py\n')
    test_update_dc_threshold()
    test_update_vertices()
    print('Tests in testbulksupplierdc.py ran to completion.\n')
