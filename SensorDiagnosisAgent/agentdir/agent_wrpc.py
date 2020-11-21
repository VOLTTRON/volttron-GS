"""
Install holidays module


"""

from __future__ import absolute_import
from datetime import datetime, timedelta, date, time
from collections import defaultdict
import logging
import sys
import grequests
import requests
from volttron.platform import jsonapi
import pytz
import pandas as pd
from dateutil.parser import parse
from volttron.platform.scheduling import cron
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent import utils
from volttron.platform.messaging import (headers as headers_mod, topics)


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.2'


class Sensor:
    """
    Container to store topics for historian query.
    """

    def __init__(self, campus, building, device, sensor_conditions):
        """
        Sensor constructor.
        :param campus:
        :param building:
        :param device:
        :param sensor_conditions:
        """

        self.diagnostic_parameters = defaultdict()
        topic = topics.RPC_DEVICE_PATH(campus=campus,
                                       building=building,
                                       unit=device,
                                       path='',
                                       point=None)
        self.device_topic = topic
        self.report_topic = {}
        self.sensors = {}
        self.evaluations = {}
        for sensor in sensor_conditions:
            self.init_sensors(topic, sensor)

    def init_sensors(self, topic, sensor):
        try:
            point_name = sensor.pop("sensor")
        except KeyError:
            _log.debug("sensor point name is missing!")
            return
        sensor_topic = topic(point=point_name)
        self.sensors[sensor_topic] = sensor
        self.evaluations[sensor_topic] = None
        self.report_topic[sensor_topic] = "/".join(["record", "SensorDiagnostic", sensor_topic])

    def update_evaluations(self, sensor_topic, _dt, fault_condition):
        evaluation = {"timestamp": _dt, "fault": fault_condition}
        if self.evaluations[sensor_topic] is None:
            self.evaluations[sensor_topic] = pd.DataFrame(evaluation)
        else:
            self.evaluations[sensor_topic].append(evaluation)

    def evaluate(self, sensor_topic):
        if self.evaluations[sensor_topic] is None:
            evaluation = self.evaluations[sensor_topic].groupby([pd.Grouper(key='Date', freq='h')]).mean()
        else:
            _log.debug("No sensor evaluations!")
            evaluation = None
        return evaluation


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
        self.station_code = "KRLD"
        self.run_schedule = "*/9 * * * *"
        self.timezone = "US/Pacific"
        self.current_config = {}
        self.tz = pytz.timezone(self.timezone)
        self.device_dict = {}
        self.weather_response = {}
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
        self.station_code = self.current_config.get("station_code", "")
        self.run_schedule = self.current_config.get("run_schedule", "")
        self.timezone = self.current_config.get("timezone", "US/Pacific")
        self.tz = pytz.timezone(self.timezone)
        sensor_conditions = self.current_config.get("sensors_condition", {})
        self.device_dict = {}
        for device, conditions in sensor_conditions.items():
            self.device_dict[device] = Sensor(campus, building, device, conditions)
        self.core.schedule(cron(self.run_schedule), self.run_diagnostics_realtime)
        self.core.schedule(cron("59 23 * * *"), self.report)

    def run_diagnostics_realtime(self):
        """
        Running sensor diagnosis
        Sensor diagnosis:
        Compare the sensor measurement with weather data; if difference between them is greather than threshold
        set  fault condition to "True"
        While performing the check, average the sensor measurment data

        TODO:The output for the agent should be similar to the EconomizerRCx agent

        """
        if not self.device_dict:
            _log.debug("No devices configured!")
            return
        _datetime = datetime.now()
        _datetime = self.tz.localize(_datetime)
        self.get_current_weather()
        for device, _cls in self.device_dict.items():
            for sensor_topic, sensor in _cls.sensors.items():
                fault_condition = self.evaulate_rule(_cls, sensor_topic, sensor)
                if fault_condition is None:
                    fault_condition = 0
                fault_condition = int(fault_condition)
                _cls.update_evaluation(sensor_topic, _datetime, fault_condition)

    def publish_report(self):
        for device, _cls in self.device_dict.items():
            for sensor_topic in _cls.sensors:
                evaluation = _cls.evaluate(sensor_topic)
                if evaluation is None:
                    continue
                report_topic = _cls.report_topic[sensor_topic]
                for index, row in evaluation.iterrows():
                    ts = utils.format_timestamp(row["timestamp"])
                    fault_condition = round(row["fault"])

                    headers = {'Date': ts}
                    message = [
                        {'fault_condition': fault_condition
                         },
                        {'fault_condition': {'tz': 'UTC', 'data_type': 'integer'}
                         }
                    ]
                    try:
                        self.vip.pubsub.publish(peer='pubsub',
                                                topic=report_topic,
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

        grequest = [grequests.get(url, verify=requests.certs.where(), headers=self.headers, timeout=5)]
        gresponse = grequests.map(grequest)[0]
        if gresponse is None:
            raise RuntimeError("get request did not return any response")
        try:
            response = jsonapi.loads(gresponse.content)
            self.weather_response = response["properties"]
        except ValueError:
            self.generate_response_error(url, gresponse.status_code)

    def evaluate_rule(self, sensor_topic, sensor):
        try:
            sensor_data = self.vip.rpc.call("platform.actuator", "get_point", sensor_topic).get(timeout=30)
        except RemoteError as ex:
            _log.warning("Failed get point for revert value storage {} (RemoteError): {}".format(sensor_topic, str(ex)))
            return
        weather_data_name = sensor.get("weather_station_name")
        if weather_data_name is not None and weather_data_name in self.weather_response:
            weather_data = self.weather_response[weather_data_name]["value"]
        else:
            _log.debug("Weather data point name: %s is not in weather data payload", weather_data_name)
            return
        threshold = sensor.get("sensor_threshold")
        return abs(sensor_data - weather_data) > threshold


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
