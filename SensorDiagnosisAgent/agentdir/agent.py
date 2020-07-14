"""
Install holidays module


"""

from __future__ import absolute_import
from collections import defaultdict
import logging
import sys
import grequests
import requests
from volttron.platform import jsonapi
import dateutil.tz
from sympy import *
from dateutil.parser import parse
from sympy.parsing.sympy_parser import parse_expr
from volttron.platform.scheduling import cron
from statistics import mean
from gevent import sleep
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent import utils
from volttron.platform.messaging import (headers as headers_mod, topics)
from datetime import datetime, timedelta, date, time
from volttron.platform.agent.base_weather import BaseWeatherAgent
import holidays
import pytz

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class SensorDiagnosisAgent(Agent):
    """
    This agent

    write a description of the agent
    """
    def __init__(self, config_path, **kwargs):
        super(SensorDiagnosisAgent, self).__init__(**kwargs)
        # Set up default configuration and config store
        self.campus = "campus"
        self.building = "building"
        self.device_list = "device"
        self.station_code = "KRLD"
        self.run_schedule = "*/3 * * * *"
        self.timezone = "US/Pacific"
        self.sensors_condition = {
            "sensor1": ["abs(OutdoorAirTemperature - temperature) > 5.0"],
            "sensor2": ["abs(OutdoorAirHumidity - relativeHumidity) > 5.0"]
        }
        self.device_point_name = ["OutdoorAirTemperature", "OutdoorAirHumidity"]
        self.weather_point_name = ["temperature", "humidity"]
        self.interval = 60
        self.device_topic_list = {}
        self.device_data = []
        self.weather_data = []
        self.default_config = utils.load_config(config_path)
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        """
        The main configuration callback.

        """
        _log.info('Received configuration {} signal: {}'.format(action, config_name))
        self.current_config = self.default_config.copy()
        self.current_config.update(contents)

        campus = self.current_config.get("campus", "")
        building = self.current_config.get("building", "")
        self.device_list = self.current_config.get("device", [])
        self.station_code = self.current_config.get("station_code", "")
        self.run_schedule = self.current_config.get("run_schedule", "")
        self.timezone = self.current_config.get("timezone", "")
        self.device_point_name = self.current_config.get("device_point_name", [])
        self.weather_point_name = self.current_config.get("weather_point_name", [])
        self.sensors_condition = self.current_config.get("sensors_condition", {})
        self.publish_topics = "/".join(["Diagnosis", self.campus, self.building])
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }
        try:
            for device_name in self.device_list:
                device_topic = topics.DEVICES_VALUE(campus=campus, building=building, \
                                                    unit=device_name, path="", \
                                                    point="all")
                self.device_topic_list.update({device_topic: device_name})
                self.device_name.append(device_name)
        except Exception as e:
            _log.error('Error configuring signal: {}'.format(e))

        for device in self.device_topic_list:
            _log.info("Subscribing to " + device)
            try:
                self.vip.pubsub.subscribe(peer="pubsub", prefix=device,
                                          callback=self.on_data)
            except Exception as e:
                _log.error('Error configuring signal: {}'.format(e))


        self.core.schedule(cron(self.run_schedule), self.run_diagnostics_realtime)

    def on_data(self, peer, sender, bus, topic, headers, message):
        """
        Subscribe to device data and assemble weather data to run sensor diagnosis.
        Sensor diagnosis:

        """

        self.input_datetime = parse(headers.get("Date"))\
            .astimezone(dateutil.tz.gettz(self.timezone))
        try:
            for args in self.device_point_name:
                self.device_data.append((args, message[0][args]))
            _log.info("device data {}".format(self.device_data))
        except Exception as e:
            _log.error('Error in subscribing device data: {}'.format(e))

    def run_diagnostics_realtime(self):
        """
        Running sensor diagnosis
        Sensor diagnosis:
        Compare the sensor measurement with weather data; if difference between them is greather than threshold
        set  fault condition to "True"
        While performing the check, average the sensor measurment data

        TODO:The output for the agent should be similar to the EconomizerRCx agent

        """
        if not self.device_data:
            return
        print("device data before average {}".format(self.device_data))
        device_data_mean = []
        for args in self.device_point_name:
            device_data_value = []
            for x in range(len(self.device_data)):
                if self.device_data[x][0] == args:
                    device_data_value.append(self.device_data[x][1])
            device_data_mean.append((args, mean(device_data_value)))

        self.device_data = device_data_mean
        self.get_current_weather()
        try:
            for args in self.weather_point_name:
                if args == 'temperature' and self.properties[args]["value"]:
                    self.weather_data.append((args,
                        self.properties[args]["value"] * (9/5) + 32))
                elif self.properties[args]["value"]:
                    self.weather_data.append((args, self.properties[args]["value"]))
                else:
                    pass
            _log.info("weather data {}".format(self.weather_data))
        except Exception as e:
            _log.error('Error in scraping weather data: {}'.format(e))

        if self.weather_data is None:
            _log.error('No weather data available: {}'.format(e))
            return

        _log.debug("Running sensor diagnosis")
        for conditions in self.sensors_condition:
            conditions = self.sensors_condition.get(conditions)
            if all([[parse_expr(condition).subs(self.device_data + self.weather_data)\
                for condition in conditions]]):
                self.fault_condition = True
                _log.debug('The Outdoor Air {} value is NOT valid.\
                 Inspect sensor location and calibration'.format(conditions))
            else:
                _log.debug("The Outdoor Air {} value is NOT valid".format(conditions))

        if self.is_midnight(self.input_datetime):
            self.publish_daily_report()
        self.publish_report()

    def publish_daily_report(self):
        headers = {'Date': utils.format_timestamp(datetime.utcnow())}
        message = [
            {'fault_condition': bool(self.fault_condition)
             },
            {'fault_condition': {'units': 's', 'tz': 'UTC', 'data_type': 'bool'}
             }
        ]
        all_topic = self.publish_topics + "/all"
        try:
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=all_topic,
                                    message=message,
                                    headers=headers)
        except Exception as e:
            _log.error("In Publish: {}".format(str(e)))

    def publish_report(self):
        headers = {'Date': utils.format_timestamp(datetime.utcnow())}
        message = [
            {'fault_condition': bool(self.fault_condition)
             },
            {'fault_condition': {'units': 's', 'tz': 'UTC', 'data_type': 'bool'}
             }
        ]
        all_topic = self.publish_topics + "/all"
        try:
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=all_topic,
                                    message=message,
                                    headers=headers)
        except Exception as e:
            _log.error("In Publish: {}".format(str(e)))

    def get_current_weather(self):
        """
        Returns current hourly weather data provided by the api via an http
        request.
        :param location: currently accepts station id (K followed by 3
        letters, case insensitive) or
        lat/long (up to 4 decimals) location dictionary formats
        :return: time of data observation as a timestamp string,
        data dictionary containing weather data points
        """
        _log.debug("Collecting current weather data")
        url = "https://api.weather.gov/stations/{}/" \
                "observations/latest".format(self.station_code)

        grequest = [grequests.get(url, verify=requests.certs.where(),
                                  headers=self.headers, timeout=5)]
        gresponse = grequests.map(grequest)[0]
        if gresponse is None:
            raise RuntimeError("get request did not return any "
                               "response")
        try:
            response = jsonapi.loads(gresponse.content)
            self.properties = response["properties"]
        except ValueError:
            self.generate_response_error(url, gresponse.status_code)

    def get_hitorian_weather(self):
        """
                Returns historian hourly weather data provided by the api via an http
                request.
                :param station_code: station code for the area.
                Can be found in weather.gov.com
                Past_time: previous time start t
                :return: time of data observation as a timestamp string,
                data dictionary containing weather data points
                """
        _log.debug("Collecting current weather data")
        url = "https://api.weather.gov/stations/{}/" \
              "observations/{}".format(self.station_code, self.past_time)

        grequest = [grequests.get(url, verify=requests.certs.where(),
                                  headers=self.headers, timeout=5)]
        gresponse = grequests.map(grequest)[0]
        if gresponse is None:
            raise RuntimeError("get request did not return any "
                               "response")
        try:
            response = jsonapi.loads(gresponse.content)
            self.properties = response["properties"]
        except ValueError:
            self.generate_response_error(url, gresponse.status_code)
        pass

    def is_midnight(self, current_time):
        midnight = datetime.combine(current_time, time.max).\
            astimezone(dateutil.tz.gettz(self.timezone))
        _log.debug("Midnight time {}".format(midnight))
        next_time = current_time+ timedelta(seconds=self.interval)
        _log.debug("next interval time {}".format(next_time))
        if midnight > next_time:
            return False
        else:
            return True

def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(SensorDiagnosisAgent, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception: {}'.format(e))


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
