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
    AFDD agent check if all conditions are true for each devices,
    if it is true then at midnight it sums the number of minute for each device
    where both conditions are true and publish a devices true time.
    if the devices true time exsits the maximum hour threshould then it flag the
    device for excess daily operating hours
    """

    def __init__(self, config_path, **kwargs):
        super(AFDDSchedulerAgent, self).__init__(**kwargs)
        # Set up default configuration and config store
        self.analysis_name = "Scheduler"
        self.campus = "campus"
        self.building = "building"
        self.device = None
        self.maximum_hour_threshold = 5.0
        self.excess_operation: False
        self.timezone = "US/Pacific"
        self.condition_list = None
        self.previous_true_time = 0

        # Set up default configuration and config store
        self.default_config = {
            "analysis_name": self.analysis_name,
            "campus": self.campus,
            "building": self.building,
            "device": self.device,
            "maximum_hour_threshold": 5.0,
            "excess_operation": False,
            "timezone": self.timezone,
            "conditions_list": None
        }

        self.device_topic_list = {}
        self.device_data = []
        self.device_status = False
        self.excess_operation = False
        self.condition_true_time_delta = 0
        self.day = None
        self.condition_data = []
        self.device_name = []
        self.simulation = True
        self.year = 2021
        self.midnight_time = None
        self.initial_time = None
        self.condition_true_time = None
        self.schedule = {"weekday_sch": ["5:30", "18:30"], "weekend_holiday_sch": ["0:00", "0:00"]}
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
        self.campus = self.current_config.get("campus")
        self.building = self.current_config.get("building")
        self.device = self.current_config.get("device", "")
        self.maximum_hour_threshold = self.current_config.get("maximum_hour_threshold")
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
        self.device_true_time = 0  # at mid night zero the total minute

    def on_subscribe(self):
        """Setup the device subscriptions"""
        # If self.device is a dict then devices contain subdevices otherwise it is a list
        multiple_devices = isinstance(self.device, dict)# check whether self.device is a dict
        if self.device:
            try:
                if multiple_devices: # create a device topic list for devices with subdevices
                    for device_name in self.device:
                        for subdevices in self.device[device_name]:
                            device_topic = topics.DEVICES_VALUE(campus=self.campus, building=self.building, \
                                                                unit=device_name, path=subdevices, \
                                                                point="all")

                            self.device_topic_list.update({device_topic: device_name})
                            self.device_name.append(device_name)

                else:
                    for device_name in self.device:
                        device_topic = topics.DEVICES_VALUE(campus=self.campus, building=self.building, \
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
                                          callback=self.time_scheduler_handler)
                # subscribe to each devices with self.time_schedule_handler
        except Exception as e:
            _log.error('Error configuring signal: {}'.format(e))
            _log.error("Missing {} data to execute the AIRx process".format(device))

    def time_scheduler_handler(self, peer, sender, bus, topic, header, message):
        """
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param header:
        :param message:
        :return: This function runs afdd schedule during unoccupied period
        """
        # if running in simulation use header datetime
        if self.simulation:
            current_time = parse(header["Date"])
        else:
            current_time = get_aware_utc_now()
        _log.debug("Simulation time handler current_time: %s", current_time)
        date_today = current_time.date()
        # check today's data is holiday or weekend.
        # if yes then use weekend schedule otherwise use weekdays schedule
        if not date_today in holidays.US(years=self.year) or date_today.weekday() == 5 and 6:
            schedule = self.schedule["weekday"]
        else:
            schedule = self.schedule["weekend_holiday"]

        self.condition_data = []
        condition_args = self.condition_list.get("condition_args")
        symbols(condition_args)
        # create a list with key(point name) and value pair
        for args in condition_args:
            self.condition_data.append((args, message[0][args]))

        _log.info("condition data {}".format(self.condition_data))
        # run afdd scheduler between unoccupied period using predefine occupied schedule
        if current_time.time() < parse(schedule[0]).time() or current_time.time() > parse(schedule[1]).time():
            self.run_schedule(current_time, topic)

    def run_schedule(self, current_time, topic):
        """

        :param current_time:
        :return: this function publishes ---
        execute the condition of the device, If all condition are true then add time into true_time.
        If true time is exceed the threshold time (maximum_hour_threshold) flag the excess operation
        """
        conditions = self.condition_list.get("conditions")
        try:
            condition_status = all([parse_expr(condition).subs(self.condition_data) for condition in conditions])
        except Exception as e:
            _log.error("Conditions are not correctly implemented in the config file : {}".format(str(e)))

        if condition_status:
            # Sum the number of minutes when both conditions are true and log each
            self.device_status = True
            if not self.condition_true_time:
                self.condition_true_time = current_time
            self.condition_true_time_delta = self.previous_true_time + (current_time - self.condition_true_time).seconds
            _log.info(f'Condition true time delta is {self.condition_true_time_delta}')
        else:
            self.condition_true_time = None
            self.device_status = False
            if self.condition_true_time_delta:
                self.previous_true_time = self.condition_true_time_delta
            _log.info("One of the condition is false")

        if (self.condition_true_time_delta / 3600) >= self.maximum_hour_threshold:
            self.excess_operation = True

        # for device_topic in self.device_topic_list:
        message = {'excess_operation': bool(self.excess_operation),
                   'device_status': bool(self.device_status)
                   }
        self.publish_analysis(topic, message, current_time)

        if self.midnight(current_time):
            message = {'device_true_time': int(self.device_true_time)}
            self.publish_analysis(topic, message, current_time)
            self.condition_true_time_delta = 0

    def midnight(self, current_time):
        """
        :param current_time:
        :return: If it is midnight returns true otherwise false
        """
        if not self.midnight_time:
            self.midnight_time = datetime.combine(current_time, time.max).\
                astimezone(dateutil.tz.gettz(self.timezone))
        if current_time >= self.midnight_time:
            self.midnight_time = datetime.combine(current_time, time.max)
            return True
        else:
            return False

    def publish_analysis(self, topic, message, current_time):
        """

        :param topic:
        :param message:
        :param current_time:
        :return: this publishes the message on the volttron message bus
        """
        headers = {'Date': format_timestamp(current_time)}
        device_topic = topic.replace("devices", self.analysis_name)

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
