"""
-*- coding: utf-8 -*- {{{
vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

Copyright (c) 2019, Battelle Memorial Institute
All rights reserved.

1.  Battelle Memorial Institute (hereinafter Battelle) hereby grants
    permission to any person or entity lawfully obtaining a copy of this
    software and associated documentation files (hereinafter "the Software")
    to redistribute and use the Software in source and binary forms, with or
    without modification.  Such person or entity may use, copy, modify, merge,
    publish, distribute, sublicense, and/or sell copies of the Software, and
    may permit others to do so, subject to the following conditions:

    -   Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimers.

    -	Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.

    -	Other than as used herein, neither the name Battelle Memorial Institute
        or Battelle may be used in any form whatsoever without the express
        written consent of Battelle.

2.	THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR
    ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
    DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
    SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
    CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
    LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
    OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
    DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.

This material was prepared as an account of work sponsored by an agency of the
United States Government. Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in the development of these
materials, makes any warranty, express or implied, or assumes any legal
liability or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed, or
represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or service by
trade name, trademark, manufacturer, or otherwise does not necessarily
constitute or imply its endorsement, recommendation, or favoring by the
United States Government or any agency thereof, or Battelle Memorial Institute.
The views and opinions of authors expressed herein do not necessarily state or
reflect those of the United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by
BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
}}}
"""
import os
import sys
import logging
from collections import defaultdict
from datetime import timedelta as td, datetime as dt
import uuid
from dateutil.parser import parse

from tcc_ilc.device_handler import ClusterContainer, DeviceClusters, parse_sympy
import pandas as pd
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod

from volttron.platform.agent.utils import setup_logging, format_timestamp, get_aware_utc_now
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.vip.agent import Agent, Core

import pandas as pd
from pandas.tseries.offsets import CustomBusinessDay, BDay
from pandas.tseries.holiday import USFederalHolidayCalendar
import pytz

__version__ = "0.2"

setup_logging()
_log = logging.getLogger(__name__)
###TODO:  Remove use of mixmarket and directly communicate demand curves for next 24 hours to TNS market
"""
1.  query data for one day for all devices and power meter [Outer loop]
2.  Group data by minute.
    3.  pass one minute of data for each device to new_data() [inner loop]
    4.  pass one minute of power meter data to load_message_handler()
    5.  load_message_handler will calculate power_min (qmin) and power_max (qmax) for that minute
        log to local sqlite db.
    6.  Go to next minute of data [step 3].
7.  Query next day of data (will query for a total of 10 business days [step 1].
8.  Using 10 days of qmin and qmax in local sqlite db use PGE approach to calculate qmin and qmax for the next 24 hours
"""
# IF we transition this to use the TNS would the inheritence change?
class TransactiveIlcCoordinator(Agent):
    def __init__(self, config_path, **kwargs):
        super(TransactiveIlcCoordinator, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        campus = config.get("campus", "")
        building = config.get("building", "")
        tz = config.get("timezone", "US/Pacific")
        logging_topic = config.get("logging_topic", "tnc")
        self.target_topic = '/'.join(['record', 'target_agent', campus, building, 'goal'])
        self.logging_topic = '/'.join([logging_topic, campus, building, "TCILC"])

        cluster_configs = config["clusters"]
        self.clusters = ClusterContainer()
        for cluster_config in cluster_configs:
            device_cluster_config = cluster_config["device_cluster_file"]
            load_type = cluster_config.get("load_type", "discreet")

            if device_cluster_config[0] == "~":
                device_cluster_config = os.path.expanduser(device_cluster_config)

            cluster_config = utils.load_config(device_cluster_config)
            cluster = DeviceClusters(cluster_config, load_type)
            self.clusters.add_curtailment_cluster(cluster)

        all_devices = self.clusters.get_device_name_list()
        self.device_query_dict = defaultdict(list)
        for device_name in all_devices:
            for device_id in self.clusters.devices[device_name].sop_args:
                for point in self.clusters.devices[device_name].sop_args[device_id]:
                    device_topic = topics.RPC_DEVICE_PATH(campus=campus,
                                                          building=building,
                                                          unit=device_name,
                                                          path="",
                                                          point=point)
                    # device_name is the same as the value needed in new_data
                    # the device topic is the same as needed for the rpc call to platform historian
                    self.device_query_dict[device_name].append(device_topic)
        _log.debug("TCILC QUERY LIST: {}".format(self.device_query_dict))

        power_token = config["power_meter"]
        power_meter = power_token["device"]
        self.power_point = power_token["point"]
        # this is local aware datetime, need to start query from historian at midnight
        # local time but the historian requires UTC.  Need to be careful here.
        self.current_datetime = config.get("start_date", dt.now(pytz.timezone(tz)))
        self.power_meter_topic = topics.RPC_DEVICE_PATH(campus=campus,
                                                        building=building,
                                                        unit=power_meter,
                                                        path="",
                                                        point=self.power_point )
        self.power_meter_device = topics.DEVICES_VALUE(campus=campus,
                                                      building=building,
                                                      unit=power_meter,
                                                      path="",
                                                      point="all")
        self.demand_limit = None
        self.bldg_power = []
        self.business_days = []
        self.power_min = None
        self.power_max = None
        self.market_prices = None
        self.average_building_power_window = td(minutes=config.get("average_building_power_window", 15))
        market_name = config.get("market", "electric")
        self.oat_predictions = []
        self.comfort_to_dollar = config.get('comfort_to_dollar', 1.0)
        self.market_name = []
        self.market_number = 24
        for i in range(self.market_number):
            self.market_name.append('_'.join([market_name, str(i)]))
            self.join_market(self.market_name[i], BUYER, None, self.offer_callback, None, self.price_callback, self.error_callback)


    @Core.receiver("onstart")
    def starting_base(self, sender, **kwargs):
        """
        Startup method:
         - Setup subscriptions to  devices.
         - Setup subscription to building power meter.
        :param sender:
        :param kwargs:
        :return:
        """
        self.make_baseline()
        _log.debug("Subscribing to " + self.power_meter_device)
        _log.debug("Subscribing to " + self.prices_topic)
        self.vip.pubsub.subscribe(peer="pubsub", prefix=self.power_meter_device, callback=self.update_time)
        self.vip.pubsub.subscribe(peer="pubsub", prefix=self.prices_topic, callback=self.update_prices)

    def make_baseline(self):
        self.get_business_days()
        # this is start of outer loop.
        for start_dt in self.business_days:
            end_dt = start_dt.replace(hour=23, minute=59, second=59)
            device_df = self.query_data(start_dt, end_dt)
            power_df = self.query_power(start_dt, end_dt)
            # Now we need to add the code to pass the data to

    def get_business_days(self):
        self.business_days = []
        for i in range(11, 1, -1):
            business_day = (self.current_datetime - BDay()).replace(hour=0, minute=0, second=0)
            self.business_days.append(business_day)

    def query_data(self, start, end, timeout=10000):
        df = None
        for device, point_topic in self.device_query_dict.items():

            result = self.vip.rpc.call('platform.historian',
                                       'query',
                                       topic=point_topic,
                                       start=start,
                                       end=end,
                                       order="FIRST_TO_LAST").get(timeout=timeout)
            #need hungs help here assume df returns data in format we need
            df2 = pd.DataFrame(result['values'], columns=[self.ts_name, point])
            df2[self.ts_name] = pd.to_datetime(df2[self.ts_name])
            df2 = df2.resample('H').mean()
            df = df2 if df is None else pd.merge(df, df2, on=self.ts_name, how='outer')
        return df

    def query_power(self, start, end, timeout=10000):
        df = None
        result = self.vip.rpc.call('platform.historian',
                                   'query',
                                   topic=self.power_meter_topic,
                                   start=start,
                                   end=end,
                                   order="FIRST_TO_LAST").get(timeout=timeout)
            # need hungs help here assume df returns data in format we need to process though new_data
            df2 = pd.DataFrame(result['values'], columns=[self.ts_name, point])
            df2[self.ts_name] = pd.to_datetime(df2[self.ts_name])
            df2 = df2.resample('H').mean()
            df = df2 if df is None else pd.merge(df, df2, on=self.ts_name, how='outer')
        return df

    def publish_demand_limit(self, demand_goal, task_id):
        """
        Publish the demand goal determined by clearing price.
        :param demand_goal:
        :param task_id:
        :return:
        """
        _log.debug("Updating demand limit: {}".format(demand_goal))
        if demand_goal is None:
            return


        self.last_demand_update = self.current_time

        start_time = format(self.current_time)
        end_time = format_timestamp(self.current_time.replace(hour=23, minute=59, second=59))
        _log.debug("Publish target: {}".format(demand_goal))
        headers = {'Date': start_time}
        target_msg = [
            {
                "value": {
                    "target": self.demand_limit,
                    "start": start_time,
                    "end": end_time,
                    "id": task_id
                    }
            },
            {
                "value": {"tz": "UTC"}
            }
        ]
        self.vip.pubsub.publish('pubsub', self.target_topic, headers, target_msg).get(timeout=15)

    def new_data(self, device_name, data):
        """

        :param self:
        :param device_name:
        :param data:
        :return:
        """
        # parsed_data needs to be a dictionary of key value pairs
        # device name is the same device name from self.device_query_dict
        parsed_data = parse_sympy(data)
        self.clusters.get_device(device_name).ingest_data(parsed_data)

    def update_time(self, peer, sender, bus, topic, headers, message):
        self.current_time = parse(headers["Date"])

    def update_prices(self, peer, sender, bus, topic, headers, message):
        _log.debug("Get prices prior to market start.")
        current_hour = message['hour']

        # Store received prices so we can use it later when doing clearing process
        if self.market_prices:
            if current_hour != self.current_time.hour:
                self.current_price = self.market_prices[0]
        self.current_hour = current_hour
        self.oat_predictions = []
        oat_predictions = message.get("temp", [])

        self.oat_predictions = oat_predictions
        self.market_prices = message['prices']  # Array of prices
        # integrate this with the TNS and remove the volttron market service dependency
        # receiving prices should trigger everything!

    def generate_price_points(self):
        if self.market_prices:
            price_min = mean(self.market_prices) - stdev(self.market_prices)*self.comfort_to_dollar
            price_max = mean(self.market_prices) + stdev(self.market_prices)*self.comfort_to_dollar
        else:
            price_min = 0.02
            price_max = 0.05
        _log.debug("TCILC PRICE - min {} - max {}".format(float(price_min), float(price_max)))
        return max(float(price_min), 0.0), float(price_max)

    def generate_power_points(self, current_power):
        positive_power, negative_power = self.clusters.get_power_bounds()
        _log.debug("TCILC POWER - pos {} - neg {}".format(positive_power, negative_power))
        return float(current_power + sum(positive_power)), float(current_power - sum(negative_power))

    def load_message_handler(self, current_power):
        """

        :param self:
        :param current_power:
        :return:
        """
        # Current power should be float
        power_max, power_min = self.generate_power_points(current_power)
        # power_max and power_min are the qmin and qmax respectively
        # log to db for later processing

    def publish_record(self, topic, message):
        headers = {headers_mod.DATE: format_timestamp(get_aware_utc_now())}
        message["TimeStamp"] = format_timestamp(self.current_time)
        self.vip.pubsub.publish("pubsub", topic, headers, message).get()


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(TransactiveIlcCoordinator)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
