"""
please install holidays module




"""

from __future__ import absolute_import
from collections import defaultdict
import logging
import sys
import csv
import dateutil.tz
from sympy import symbols
from datetime import datetime as dt, timedelta as td
from dateutil.parser import parse
from random import random
from sympy.parsing.sympy_parser import parse_expr
from gevent import sleep
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent import utils
from volttron.platform.messaging import (headers as headers_mod, topics)
from datetime import datetime, timedelta, date, time
import holidays
import pytz

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
        self.actuation_mode = "PASSIVE"
        self.actuator_lock_required = False
        self.arguments = {
            "points": {
                       'ReturnAirTemperature',
                       'SupplyFanStatus'
                       },
            "device_type": "rtu",
            "mht": 5.0
        }
        self.timezone = "US/Pacific"
        self.default_write_attempts = 1
        self.condition_list = None

        # Set up default configuration and config store
        self.default_config = {
            "analysis_name": self.analysis_name,
            "device": self.device,
            "actuation_mode": self.actuation_mode,
            "require_actuator_check": self.actuator_lock_required,
            "arguments": self.arguments,
            "timezone": self.timezone,
            "default_write_attempts": self.default_write_attempts,
            "conditions_list":None
        }
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

        self.analysis_name = self.current_config.get("analysis_name")
        self.device = self.current_config.get("device")
        self.actuation_mode = self.current_config.get("actuation_mode")
        self.actuator_lock_required = self.current_config.get("require_actuator_check")
        self.arguments = self.current_config.get("arguments")
        self.actuation_mode = True if self.current_config.get("actuation_mode", "PASSIVE") == "ACTIVE" else False
        self.actuator_lock_required = self.current_config.get("require_actuator_lock", False)
        self.default_write_attempts = self.current_config.get("default_write_attempts")
        self.timezone = self.current_config.get("timezone")
        self.condition_list = self.current_config.get("condition_list", {})

        self.excess_operation = False
        self.rtu_true = timedelta(minutes=0)
        self.rtu_false = timedelta(minutes=0)

        campus = self.device["campus"]
        building = self.device["building"]
        points = self.arguments["points"]
        self.publish_topics = "/".join([self.analysis_name, campus, building])
        device_config = self.device["unit"]
        multiple_devices = isinstance(device_config, dict)
        self.command_devices = device_config.keys()
        self.device_topic_dict = {}
        self.device_topic_list = []
        self.subdevices_list = []
        self.interval = timedelta(minutes=1)
        self.rthr = timedelta(hours=0)

        if self.condition_list:
            self.initialize_condition(self.condition_list)
        else:
            _log.debug("No diagnostic prerequisites configured!")

        try:
            for device_name in device_config:
                device_topic = topics.DEVICES_VALUE(campus=campus, building=building, \
                                                    unit=device_name, path="", \
                                                    point="all")

                self.device_topic_dict.update({device_topic: device_name})
                self.device_topic_list.append(device_name)
                if multiple_devices:
                    for subdevice in device_config[device_name]["subdevices"]:
                        self.subdevices_list.append(subdevice)
                        subdevice_topic = topics.DEVICES_VALUE(campus=campus, \
                                                               building=building, \
                                                               unit=device_name, \
                                                               path=subdevice, \
                                                               point="all")

                        subdevice_name = device_name + "/" + subdevice
                        self.device_topic_dict.update({subdevice_topic: subdevice_name})
                        self.device_topic_list.append(subdevice_name)

        except Exception as e:
            _log.error('Error configuring signal: {}'.format(e))

        self.base_actuator_path = topics.RPC_DEVICE_PATH(campus=campus, building=building, \
                                                         unit=None, path="", point=None)

        for device in self.device_topic_dict:
            _log.info("Subscribing to " + device)
            try:
                self.vip.pubsub.subscribe(peer="pubsub", prefix=device, \
                                          callback=self.on_schedule)
            except Exception as e:
                _log.error('Error configuring signal: {}'.format(e))

    def initialize_condition(self, condition_list):
        """Initialize and store information associated with evaluation
        of the diagnostic prerequisites.
        :param prerequisites: dictionary with information associated
        with diagnostic prerequisites.
        :return: None
        """
        # list of point name associated with diagnostic prerequisites
        # data is recieved in new_data method and subscriptions to device
        # data are made in starting_base
        condition_args = condition_list.get("condition_args")
        # List of rules to evaluate to determine if conditions permit
        # running the proactive diagnostics.
        condition_list = condition_list.get("conditions")
        for point in condition_args:
            self.condition_data_required[point] = []
        self.condition_variables = symbols(condition_args)
        for prerequisite in condition_list:
            self.condition_expr_list.append(parse_expr(prerequisite))

    @Core.receiver("onstart")
    def on_start(self, sender, **kwarge):
        _log.info('Starting AgentTemplateAgent.')

#   @Core.receiver("onstop")
#    def on_stop(self, sender):
#       _log.info('Stopping AgentTemplateAgent.')

    def is_weekday(self, current_time):
        print(current_time.weekday())
        if current_time.weekday()== 6 and 7:
            return False
        else:
            return True
    def is_holiday(self, current_time):
        if current_time in holidays.US(years=2020):
           return current_time.da


    def is_midnight(self, current_time):
        midnight = datetime.combine(current_time, time.max).\
            astimezone(dateutil.tz.gettz(self.timezone))
        _log.debug("Midnight time {}".format(midnight))
        next_time = current_time + self.interval
        _log.debug("next interval time {}".format(next_time))
        if midnight > next_time:
            return False
        else:
            return True

    def all_condition_true(self, current_time):
        pass

    def on_schedule(self, peer, sender, bus, topic, headers, message):
        """
        Subscribe to device data and assemble data set to pass
            to applications.
        """
        self.input_datetime = parse(headers.get("Date"))\
            .astimezone(dateutil.tz.gettz(self.timezone))

        _log.debug("Current time of publish: {}".format(self.input_datetime))
        _log.debug("Current device topic: {}".format(topic))

        device_data = {}

        for key, value in message[0].items():
            device_data_tag = topic.replace("all",key)
            device_data[device_data_tag] = value
            #_log.debug('device data for {} is {}'.format(device_data_tag, value)

        _log.debug('device data {}'.format(device_data))
        try:
            status = message[0]['SupplyFanStatus']
            _log.debug('status supplyfan {}'.format(status))
        except:
            _log.error("Missing 'SupplyFanStatus' data to execute the AIRx process")
            #remeber previous value of status

        try:
            return_temp = message[0]['ReturnAirTemperature']
            _log.debug('return temp {}'.format(return_temp))
        except:
            _log.error("Missing 'ReturnAirTemperture' data to execute the AIRx process")

        if status and return_temp > self.arguments["rat_low_threshold"]\
                    and return_temp < self.arguments["rat_high_threshold"]:
            self.rtu_true += self.interval
            _log.debug('rtu all condition true time {}'.format(self.rtu_true ))
        else:
            #self.set_point(topic.replace("all",'SupplyFanStatus'),0)
            # set rtu_status to False
            _log.info('status of supply fan set to False')

        rthr = self.rtu_true.total_seconds()/3600

        if rthr > self.arguments["mht"]:
            self.excess_operation = True

        if self.is_midnight(self.input_datetime):
            print("main mid night function mai hun")
            self.rtu_true = timedelta(minutes=0)
            self.publish(rthr)

    def process(self, results):
        pass

    def publish(self, results):
        # Build message.
        """
        What topics are you going to publish?
        excess_operation?
        rtmr for a day?
        rthr for a day?

        """
        headers = {'Date': utils.format_timestamp(datetime.utcnow())}

        try:
            self.vip.pubsub.publish("pubsub", self.publish_topics, headers, results)
        except Exception as e:
            _log.error("In Publish: {}".format(str(e)))



    def set_point(self, point, value, check_response=True, tries=None):
        failed = False
        set_result = False
        tries_remaining = tries if tries else self.default_write_attempts
        while tries_remaining > 0:
            try:
                set_result = self.vip.rpc.call(
                    'platform.actuator',
                    'set_point',
                    self.core.identity,
                    point,
                    value
                ).get()
                break
            except Exception as e:
                set_result = e
                tries_remaining -= 1
                if tries_remaining > 0:
                    _log.warning('{} tries remaining of {} - got exception {} while setting {}'.format(
                        tries_remaining, tries, set_result, point))
                    sleep(random())
                else:
                    failed = True
                continue
        if check_response and set_result != value:
            failed = True
        if failed:
            _log.error('Failed to set {} to {}. Received {} from set operation.'.format(
                point, value, set_result))
            return False
        elif check_response:
            return True
        else:
            # If not checking response here, return it for the caller.
            return set_result


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
