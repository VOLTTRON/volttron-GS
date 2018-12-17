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


import os
import csv
from datetime import datetime, timedelta
from dateutil import parser

from information_service_model import InformationServiceModel
from measurement_type import MeasurementType
from measurement_unit import MeasurementUnit
from interval_value import IntervalValue

from volttron.platform.agent import utils


class TemperatureForecastModel(InformationServiceModel, object):
    """
    Predict hourly temperature (F)
    Use CSV as we don't have internet access for now. Thus keep the csv file as small as possible
    This can be changed to read from real-time data source such as WU
    """

    def __init__(self, config_path):
        super(TemperatureForecastModel, self).__init__()
        self.config = utils.load_config(config_path)
        self.weather_file = self.config.get('weather_file')

        self.predictedValues = []
        self.weather_data = []
        self.last_modified = None

        self.init_weather_data()

    def init_weather_data(self):
        """
        To init or re-init weather data from file.
        :return:
        """
        # Get latest modified time
        cur_modified = os.path.getmtime(self.weather_file)

        if self.last_modified is None or cur_modified != self.last_modified:
            self.last_modified = cur_modified

            # Clear weather_data for re-init
            self.weather_data = []

            # Extract data from weather file
            with open(self.weather_file) as f:
                reader = csv.DictReader(f)
                self.weather_data = [r for r in reader]
                for rec in self.weather_data:
                    rec['Timestamp'] = parser.parse(rec['Timestamp']).replace(minute=0, second=0, microsecond=0)
                    rec['Value'] = float(rec['Value'])

    def update_information(self, mkt):
        self.init_weather_data()

        # Copy weather data to predictedValues
        self.predictedValues = []
        for ti in mkt.timeIntervals:
            # Find item which has the same timestamp as ti.timeStamp
            start_time = ti.startTime.replace(minute=0)
            items = [x for x in self.weather_data if x['Timestamp'] == start_time]
            if len(items) == 0:
                trial_deltas = [-1, 1, -2, 2, -24, 24]
                for delta in trial_deltas:
                    items = [x for x in self.weather_data if x['Timestamp'] == (start_time-timedelta(hours=delta))]
                    if len(items) > 0:
                        break

                # None exist, raise exception
                if len(items) == 0:
                    raise Exception('No weather data for time: {}'.format(utils.format_timestamp(ti.startTime)))

            # Create interval value and add it to predicted values
            temp = items[0]['Value']
            interval_value = IntervalValue(self, ti, mkt, MeasurementType.PredictedValue, temp)
            self.predictedValues.append(interval_value)


if __name__ == '__main__':
    from market import Market
    import helpers

    forecaster = TemperatureForecastModel('/home/hngo/PycharmProjects/volttron-applications/pnnl/TNSAgent/campus_config.json')

    # Create market with some time intervals
    mkt = Market()
    mkt.marketClearingTime = datetime.now().replace(minute=0, second=0, microsecond=0)
    mkt.nextMarketClearingTime = mkt.marketClearingTime + mkt.marketClearingInterval

    mkt.check_intervals()

    # Test update_information
    forecaster.update_information(mkt)

    times = [helpers.format_ts(x.timeInterval.startTime) for x in forecaster.predictedValues]

    print(times)
