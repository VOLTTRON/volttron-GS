"""


"""

from __future__ import absolute_import
import logging
import sys
import dateutil.tz
from sympy import *
from dateutil.parser import parse
from sympy.parsing.sympy_parser import parse_expr
from sympy.logic.boolalg import BooleanFalse, BooleanTrue
from gevent import sleep
from volttron.platform.scheduling import cron, periodic
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from datetime import datetime, timedelta, date, time
import holidays
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)
from volttron.platform.scheduling import cron
from dateutil import parser

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class AFDDSchedulerAgent(Agent):
    """
    This agent

    write a description of the agent
    """

    def __init__(self, config_path, **kwargs):
        super(AFDDSchedulerAgent, self).__init__(**kwargs)
        # Set up default configuration and config store
        self.analysis_name = "Scheduler"
        self.schedule_time = "* 18 * * *"
        self.device = {
            "campus": "campus",
            "building": "building",
            "unit": {
                "rtu1": {
                    "subdevices": []
                },
                "rtu4": {
                    "subdevices": []
                }
            }
        }
        self.maximum_hour_threshold = 5.0
        self.excess_operation: False
        self.interval: 60
        self.timezone = "US/Pacific"
        self.condition_list = None

        # Set up default configuration and config store
        self.default_config = {
            "analysis_name": self.analysis_name,
            "schedule_time": self.schedule_time,
            "device": self.device,
            "mht": 3600,
            "excess_operation": False,
            "interval": 60,
            "timezone": self.timezone,
            "conditions_list": None
        }

        self.device_topic_list = {}
        self.device_data = []
        self.device_true_time = 0
        self.subdevices_list = []
        self.device_status = False
        self.excess_operation = False
        self.day = None
        self.condition_data = []
        self.rthr = 0
        self.device_name = []
        self.simulation = True
        self.year = 2021
        self.schedule = {"weekday_sch": ["5:30","18:30"], "weekend_holiday_sch": ["0:00","0:00"]}
        self.default_config = utils.load_config(config_path)
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], \
                                  pattern="config")

    def configure(self, config_name, action, contents):
        """
        The main configuration callback.

        """
        _log.info('Received configuration {} signal: {}'.format(action, config_name))
        self.current_config = self.default_config.copy()
        self.current_config.update(contents)

        self.analysis_name = self.current_config.get("analysis_name")
        self.schedule_time = self.current_config.get("schedule_time")
        self.device = self.current_config.get("device")
        self.maximum_hour_threshold = self.current_config.get("mht")
        self.excess_operation = self.current_config.get("excess_operation")
        self.timezone = self.current_config.get("timezone", "PDT")
        self.condition_list = self.current_config.get("condition_list", {})
        self.simulation = self.current_config.get("simulation", True)
        self.year = self.current_config.get("year", 2021)
        self.schedule = self.current_config.get("schedule", "")
        self.device_true_time = 0
        _log.info("current date time {}".format(datetime.utcnow()))
        self.on_subscribe()
        # self.core.periodic(self.interval, self.run_schedule)
        self.device_true_time = 0 #at mid night zero the total minute

    def on_subscribe(self):
        _log.debug("Running with simulation using topic %s",
                   self.simulation_data_topic)

        campus = self.device["campus"]
        building = self.device["building"]
        device_config = self.device["unit"]
        self.publish_topics = "/".join([self.analysis_name, campus, building])
        multiple_devices = isinstance(device_config, dict)
        self.command_devices = device_config.keys()

        try:
            for device_name in device_config:
                device_topic = topics.DEVICES_VALUE(campus=campus, building=building, \
                                                    unit=device_name, path="", \
                                                    point="all")

                self.device_topic_list.update({device_topic: device_name})
                self.device_name.append(device_name)

        except Exception as e:
            _log.error('Error configuring device topic {}'.format(e))

        try:
            for device in self.device_topic_list:
                _log.info("Subscribing to " + device)
                self.vip.pubsub.subscribe(peer="pubsub", prefix=device,
                                          callback=self.scheduler_time_handler)
        except Exception as e:
            _log.error('Error configuring signal: {}'.format(e))
            _log.error("Missing {} data to execute the AIRx process".format(device))

    def scheduler_time_handler(self, peer, sender, bus, topic, header, message):
        if self.simulation:
            current_time = parse(header["Date"])
        else:
            current_time = get_aware_utc_now()
        _log.debug("Simulation time handler current_time: %s", current_time)
        date_today = current_time.date()
        if date_today in holidays.US(years=self.year) or date_today.weekday() == 5 and 6:
            schedule = self.schedule["weekday"]
        else:
            schedule = self.schedule["weekend_holiday"]

        self.condition_data = []
        condition_args = self.condition_list.get("condition_args")
        symbols(condition_args)

        for args in condition_args:
            self.condition_data.append((args, message[0][args]))

        _log.info("condition data {}".format(self.condition_data))
        # convert all the required data into a dict
        if current_time.time() < parse(schedule[0]).time() or current_time.time() > parse(schedule[1]).time():
            self.run_schedule(current_time)

    def run_schedule(self, current_time):
        """
        execute the condition of the device, If all condition are true then add time into true_time.
        If true time is exceed the threshold time (mht) flag the excess operation
        TODO:The output for the agent should be similar to the EconomizerRCx agent
        """
        conditions = self.condition_list.get("conditions")
        try:
            condition_status = all([parse_expr(condition).subs(self.condition_data) for condition in conditions])
        except Exception as e:
            _log.error("Conditions are not correctly implemented in the config file : {}".format(str(e)))

        if condition_status:
            # Sum the number of minutes when both conditions are true and log each day
            self.device_true_time += self.interval
            self.device_status = True
            _log.Info('All condition true time {}'.format(self.device_true_time))
        else:
            self.device_status = False
            _log.Info("one of the condition is false")

        runtime_threshold = self.device_true_time / 3600
        if runtime_threshold > self.maximum_hour_threshold:
            self.excess_operation = True

        for device_topic in self.device_topic_list:
            self.publish_daily_record(device_topic, current_time)

    def publish_daily_record(self, device_topic, current_time):
        headers = {'Date': format_timestamp(current_time)}
        message = {'excess_operation': bool(self.excess_operation),
                   'device_status': bool(self.device_status),
                   'device_true_time': int(self.device_true_time)}
        device_topic = device_topic.replace("all", "report/all")
        try:
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=device_topic,
                                    message=message,
                                    headers=headers)
        except Exception as e:
            _log.error("In Publish: {}".format(str(e)))

    def get_point(self, point, tries=None):
        """
        This function will get point value using RPC calll
        :param point: point
        :param tries:
        :return: value
        """
        tries_remaining = tries if tries else self.default_write_attempts
        while tries_remaining > 0:
            try:
                value = self.vip.rpc.call(
                    'platform.actuator',
                    'get_point',
                    point
                ).get()
                return value
            except Exception as e:
                tries_remaining -= 1
                _log.warning("{} tries remaining of {}, got exception {} while getting {}".format(
                    tries_remaining, tries, point, str(e)))
                sleep(3)
                continue
        return False



def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(AFDDSchedulerAgent, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception: {}'.format(e))


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
