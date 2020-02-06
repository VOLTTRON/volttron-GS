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
import logging
from datetime import datetime, timedelta
from dateutil import parser
import dateutil.tz


class WeatherService(object):
    """
    Predict hourly temperature (F)
    Use CSV as we don't have internet access for now. Thus keep the csv file as small as possible
    This can be changed to read from real-time data source such as WU
    """

    def __init__(self, weather_file=None):
        self.weather_file = weather_file

        self.predicted_values = []
        self.weather_data = []
        self.last_modified = None
        try:
           self.localtz = dateutil.tz.tzlocal()
        except:
            # Problem automatically determining timezone! - Default to UTC
            self.localtz = "UTC"

        # Load weather data the 1st time
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

            with open(self.weather_file) as f:
                reader = csv.DictReader(f)
                self.weather_data = [r for r in reader]
                for rec in self.weather_data:
                    rec['Timestamp'] = parser.parse(rec['Timestamp']).replace(minute=0, second=0, microsecond=0)
                    rec['Value'] = float(rec['Value'])

    def predict(self, times):
        self.init_weather_data()

        # Copy weather data to predictedValues
        self.predicted_values = []
        for start_time in times:
            items = [x for x in self.weather_data if x['Timestamp'] == start_time]
            if len(items) == 0:
                trial_deltas = [-1, 1, -2, 2, -24, 24]
                for delta in trial_deltas:
                    items = [x for x in self.weather_data if x['Timestamp'] == (start_time - timedelta(hours=delta))]
                    if len(items) > 0:
                        break

                # None exist, raise exception
                if len(items) == 0:
                    raise Exception('No weather data for time: {}'.format(start_time))

            temp = items[0]['Value']
            self.predicted_values.append(temp)

        return self.predicted_values


if __name__ == '__main__':
    from datetime import timedelta

    now = datetime.now()
    next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    times = []
    for i in range(0, 24):
        times.append(next_day + timedelta(hours=i))

    ws = WeatherService(
        weather_file="/Users/ngoh511/Documents/projects/volttron-GS/Market3Agent/market3/weather_data/energyplus.csv")
    temps = ws.predict(times)

    print(temps)
    print(len(temps))
