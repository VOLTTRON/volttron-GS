import logging
import gevent
import dateutil.tz
import numpy as np
from volttron.platform.agent.utils import setup_logging
from dateutil.parser import parse
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent import errors
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.utils import setup_logging, format_timestamp, get_aware_utc_now

_log = logging.getLogger(__name__)
setup_logging()
__version__ = '0.1'

class DeviceControlBase(object):

    def __init__(self, config, vip_object, topic_prefix):
        self.current_datetime = None
        self.current_schedule = None
        self.actuation_enabled = False
        self.actuation_disabled = False
        self.inputs = {}
        self.outputs = {}
        self.schedule = {}
        self.occupied = False
        self.actuation_obj = None
        self.current_datetime = None
        self.input_topics = []
        self.vip_obj = vip_object
        self.topic_prefix = topic_prefix
        input_data_tz = config.get("input_data_timezone", "UTC")
        self.input_data_tz = dateutil.tz.gettz(input_data_tz)
        self.agent_name = ''

        campus = config.get("campus", "")
        building = config.get("building", "")

        # set actuation parameters for device control
        actuate_topic = config.get("actuation_enable_topic", "default")
        if actuate_topic == "default":
            self.actuate_topic = '/'.join([campus, building, 'actuate'])
        else:
            self.actuate_topic = actuate_topic
        self.actuate_onstart = config.get("actuation_enabled_onstart", False)
        self.actuation_method = config.get("actuation_method", "periodic")
        self.actuation_rate = config.get("control_interval", 300)
        inputs = config.get("inputs", [])
        self._outputs = config.get("outputs", [])
        self.init_inputs(inputs)
        schedule = config.get("schedule", {})
        self.init_schedule(schedule)

    def input_subscriptions(self):
        for topic in self.input_topics:
            _log.debug('Subscribing to: ' + topic)
            self.vip_obj.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                      callback=self.update_input_data)

    def init_actuation_state(self, actuate_topic, actuate_onstart):
        if self._outputs:
            self.vip_obj.pubsub.subscribe(peer='pubsub',
                                      prefix=actuate_topic,
                                      callback=self.update_actuation_state)
            if actuate_onstart:
                self.update_actuation_state(None, None, None, None, None, True)
                self.actuation_disabled = False
        else:
            _log.info("{} - cannot initialize actuation state, no configured outputs.".format(self.agent_name))

    def init_schedule(self, schedule):
        if schedule:
            for day_str, schedule_info in schedule.items():
                _day = parse(day_str).weekday()
                if schedule_info not in ["always_on", "always_off"]:
                    start = parse(schedule_info["start"]).time()
                    end = parse(schedule_info["end"]).time()
                    self.schedule[_day] = {"start": start, "end": end}
                else:
                    self.schedule[_day] = schedule_info

    def check_schedule(self, dt):
        current_schedule = self.schedule[dt.weekday()]
        if "always_on" in current_schedule:
            self.occupied = True
            if not self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, True)
            return
        if "always_off" in current_schedule:
            self.occupied = False
            if self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, False)
            return
        _start = current_schedule["start"]
        _end = current_schedule["end"]
        if _start < self.current_datetime.time() < _end:
            self.occupied = True
            if not self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, True)
        else:
            self.occupied = False
            if self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, False)

    def check_future_schedule(self, dt):
        current_schedule = self.schedule[dt.weekday()]
        if "always_on" in current_schedule:
            return True
        if "always_off" in current_schedule:
            return False
        _start = current_schedule["start"]
        _end = current_schedule["end"]
        if _start < dt.time() < _end:
            return True
        else:
            return False

    def update_actuation_state(self, peer, sender, bus, topic, headers, message):
        state = message
        if self.actuation_disabled:
            if sender is None:
                _log.debug("{} is disabled not change in actuation state".format(self.agent_name))
                return
            elif bool(state):
                _log.debug("{} is re-enabled for actuation.".format(self.agent_name))
                self.actuation_disabled = False
        if not self.actuation_disabled:
            if sender is not None and not bool(state):
                _log.debug("{} is disabled for actuation.".format(self.agent_name))
                self.actuation_disabled = True

        _log.debug("update actuation {}".format(state))
        if self.actuation_enabled and not bool(state):
            for output_info in self.outputs.values():
                topic = output_info["topic"]
                release = output_info["release"]
                actuator = output_info["actuator"]
                if self.actuation_obj is not None:
                    self.actuation_obj.kill()
                    self.actuation_obj = None
                self.actuate(topic, release, actuator)
        elif not self.actuation_enabled and bool(state):
            for name, output_info in self.outputs.items():
                offset = output_info.get("offset", 0.0)
                actuator = output_info.get("actuator", "platform.actuator")
                topic = output_info["topic"]
                release = output_info.get("release", None)
                if isinstance(release, str) and release.lower() == "default":
                    try:
                        release_value = self.vip_obj.rpc.call(actuator,
                                                          'get_point',
                                                          topic).get(timeout=10)
                    except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
                        _log.warning("Failed to get {} - ex: {}".format(topic, str(ex)))
                else:
                    release_value = None
                self.outputs[name]["release"] = release_value

            self.actuation_enabled = state

    def update_input_data(self, peer, sender, bus, topic, headers, message):
        data = message[0]
        current_datetime = parse(headers.get("Date"))
        self.current_datetime = current_datetime.astimezone(self.input_data_tz)
        self.update_data(data)
        if current_datetime is not None and self.schedule:
            self.check_schedule(current_datetime)

    def update_data(self, data):
        to_publish = {}
        for name, input_data in self.inputs.items():
            for point, value in input_data.items():
                if point in data:
                    self.inputs[name][point] = data[point]
                    to_publish[point] = data[point]
        topic_suffix = "/".join([self.agent_name, "InputData"])
        message = to_publish
        self.publish_record(topic_suffix, message)
        self.model.update_data()

    def actuate(self, point_topic, value, actuator):
        try:
            self.vip_obj.rpc.call(actuator,
                                  'set_point',
                                  "",
                                  point_topic,
                                  value).get(timeout=10)
        except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
            _log.warning("Failed to set {} - ex: {}".format(point_topic, str(ex)))

    def actuate(self, output_dict):
        point_topic = output_dict["topic"]
        point = output_dict["point"]
        actuator = output_dict["actuator"]
        value = output_dict.get("value")
        offset = output_dict["offset"]
        if value is not None:
            value = value + offset
            try:
                self.vip_obj.rpc.call(actuator,
                                  'set_point',
                                  "",
                                  point_topic,
                                  value).get(timeout=10)
            except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
                _log.warning("Failed to set {} - ex: {}".format(point_topic, str(ex)))

    def determine_sched_index(self, index):
        if self.current_datetime is None:
            return index
        elif index + self.current_datetime.hour + 1 < 24:
            return self.current_datetime.hour + index + 1
        else:
            return self.current_datetime.hour + index + 1 - 24

    def get_input_value(self, mapped):
        try:
            return self.inputs[mapped].values()[0]
        except KeyError:
            return None

    def init_inputs(self, inputs):
        for input_info in inputs:
            point = input_info.pop("point")
            mapped = input_info.pop("mapped")
            topic = input_info.pop("topic")
            value = input_info.pop("inital_value")
            self.inputs[mapped] = {point: value}
            if topic not in self.input_topics:
                self.input_topics.append(topic)

    def init_outputs(self, outputs):
        for output_info in outputs:
            # Topic to subscribe to for data (currently data format must be
            # consistent with a MasterDriverAgent all publish)
            topic = output_info["topic"]
            # Point name from as published by MasterDriverAgent
            point = output_info.pop("point")
            mapped = output_info.pop("mapped")
            # Options for release are None or default
            # None assumes BACnet release via priority array
            # default will safe original value, at start of agent run for control restoration
            # TODO: Update release value anytime agent has state tranistion for actuation_enable
            release = output_info.get("release", None)
            # Constant offset to apply to apply to determined actuation value
            offset = output_info.get("offset", 0.0)
            # VIP identity of Actuator to call via RPC to perform control of device
            actuator = output_info.get("actuator", "platform.actuator")
            # This is the flexibility range for the market commodity the
            # transactive agent will utilize
            flex = output_info["flexibility_range"]
            # This is the flexibility of the control point, by default the same as the
            # market commodity but not necessarily
            ct_flex = output_info.get("control_flexibility", flex)
            ct_flex = np.linspace(ct_flex[0], ct_flex[1], 11)
            flex = np.linspace(flex[0], flex[1], 11)
            fallback = output_info.get("fallback", mean(ct_flex))
            # TODO:  Use condition to determine multiple output scenario
            condition = output_info.get("condition", True)

            try:
                value = self.vip_obj.rpc.call(actuator,
                                          'get_point',
                                          topic).get(timeout=10)
            except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
                _log.warning("Failed to get {} - ex: {}".format(topic, str(ex)))
                value = fallback
            if isinstance(release, str) and release.lower() == "default" and value is not None:
                release_value = value
            else:
                release_value = None
            off_setpoint = output_info.get("off_setpoint", value)
            self.outputs[mapped] = {
                "point": point,
                "topic": topic,
                "actuator": actuator,
                "release": release_value,
                "value": value,
                "off_setpoint": off_setpoint,
                "offset": offset,
                "flex": flex,
                "ct_flex": ct_flex,
                "condition": condition
            }

    def publish_record(self, topic_suffix, message):
        headers = {headers_mod.DATE: format_timestamp(get_aware_utc_now())}
        message["TimeStamp"] = format_timestamp(self.current_datetime)
        topic = "/".join([self.topic_prefix, topic_suffix])
        self.vip_obj.pubsub.publish("pubsub", topic, headers, message).get()
