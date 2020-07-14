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
from volttron.platform.scheduling import cron
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from datetime import datetime, timedelta, date, time
import holidays

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
        self.mht: 5.0
        self.excess_operation: false
        self.interval: 60
        self.timezone = "US/Pacific"
        self.condition_list = None

        # Set up default configuration and config store
        self.default_config = {
            "analysis_name": self.analysis_name,
            "schedule_time": self.schedule_time,
            "device": self.device,
            "mht": 3600,
            "excess_operation": false,
            "interval": 60,
            "timezone": self.timezone,
            "conditions_list": None
        }

        self.device_topic_list = {}
        self.device_data = []
        # self.device_topic_list = []
        self.subdevices_list = []
        self.device_status = False
        self.day = None
        self.condition_data = []
        self.rthr = 0
        self.device_name = []

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
        self.mht = self.current_config.get("mht")
        self.excess_operation = self.current_config.get("excess_operation")
        self.interval = self.current_config.get("interval")
        self.timezone = self.current_config.get("timezone")
        self.condition_list = self.current_config.get("condition_list", {})
        self.device_true_time = 0

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
            _log.error('Error configuring signal: {}'.format(e))

        date_today = datetime.utcnow().astimezone(dateutil.tz.gettz(self.timezone))
        print(date_today)
        if date_today in holidays.US(years=2020) or date_today.weekday() == 5 and 6:
            schedule_time = "* * * * *"
            self.core.schedule(cron(schedule_time), self.run_schedule)
        else:
            self.core.schedule(cron(self.schedule_time), self.run_schedule)

    def run_schedule(self):
        _log.info("current date time {}".format(datetime.utcnow()))
        try:
            for device in self.device_topic_list:
                _log.info("Subscribing to " + device)
                self.vip.pubsub.subscribe(peer="pubsub", prefix=device,
                                          callback=self.on_data)
        except Exception as e:
            _log.error('Error configuring signal: {}'.format(e))
            _log.error("Missing {} data to execute the AIRx process".format(device))
        # self.core.periodic(self.interval, self.on_schedule)
        if self.condition_data:
            self.on_schedule()

    def on_data(self, peer, sender, bus, topic, headers, message):
        """
        Subscribe device data.

        """
        self.condition_data = []
        self.input_datetime = parse(headers.get("Date")) \
            .astimezone(dateutil.tz.gettz(self.timezone))
        condition_args = self.condition_list.get("condition_args")
        symbols(condition_args)

        for args in condition_args:
            self.condition_data.append((args, message[0][args]))

        _log.info("condition data {}".format(self.condition_data))

    def on_schedule(self):
        """
        execute the condition of the device, If all condition are true then add time into true_time.
        If true time is excedd the threshold time (mht) flag the excess operation

        """
        conditions = self.condition_list.get("conditions")
        if all([parse_expr(condition).subs(self.condition_data) \
                for condition in conditions]):
            self.device_true_time += self.interval
            self.device_status = True
            _log.debug('All condition true time {}'.format(self.device_true_time))
        else:
            self.device_status = False
            _log.debug("one of the condition is false")

        rthr = self.device_true_time / 3600
        if rthr > self.mht:
            self.excess_operation = True

        if self.is_midnight(self.input_datetime):
            self.device_true_time = 0
            for device_topic in self.device_topic_list:
                print(device_topic)
                self.publish(device_topic)

    def publish(self, device_topic):
        headers = {'Date': utils.format_timestamp(datetime.utcnow() \
                                                  .astimezone(dateutil.tz.gettz(self.timezone)))}
        message = [
            {'excess_operation': bool(self.excess_operation),
             'device_status': bool(self.device_status),
             'device_true_time': int(self.device_true_time)
             },
            {'excess_operation': {'units': 'None', 'tz': 'UTC', 'data_type': 'bool'},
             'device_status': {'units': 'None', 'tz': 'UTC', 'data_type': 'bool'},
             'device_true_time': {'units': 'seconds', 'tz': 'UTC', 'data_type': 'integer'}
             }
        ]
        device_topic = device_topic.replace("all", "report/all")
        try:
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=device_topic,
                                    message=message,
                                    headers=headers)
        except Exception as e:
            _log.error("In Publish: {}".format(str(e)))

    def is_midnight(self, current_time):
        midnight = datetime.combine(current_time, time.max). \
            astimezone(dateutil.tz.gettz(self.timezone))
        _log.debug("Midnight time {}".format(midnight))
        next_time = current_time + timedelta(seconds=self.interval)
        _log.debug("next interval time {}".format(next_time))
        if midnight > next_time:
            return False
        else:
            return True


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
