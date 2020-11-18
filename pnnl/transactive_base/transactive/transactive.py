import logging
import sys
from datetime import timedelta as td
import numpy as np

from dateutil.parser import parse
from datetime import datetime as dt
import dateutil.tz
import gevent
from collections import OrderedDict
from volttron.pnnl.transactive_base.transactive.markets import DayAheadMarket
from volttron.pnnl.transactive_base.transactive.markets import RealTimeMarket
from volttron.pnnl.transactive_base.transactive.utils import calculate_hour_of_year, lists_to_dict
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.utils import setup_logging, format_timestamp, get_aware_utc_now
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent import errors

from volttron.pnnl.models import Model
_log = logging.getLogger(__name__)
setup_logging()
__version__ = '0.4'


class TransactiveBase(MarketAgent, Model):
    def __init__(self, config, aggregator=None, **kwargs):
        MarketAgent.__init__(self, **kwargs)
        default_config = {
            "campus": "",
            "building": "",
            "device": "",
            "agent_name": "",
            "actuation_method": "periodic",
            "control_interval": 900,
            "market_name": "electric",
            "input_data_timezone": "UTC",
            "actuation_enable_topic": "tnc/actuate",
            "actuation_enabled_onstart": False,
            "price_multiplier": 1.0,
            "inputs": [],
            "outputs": [],
            "schedule": {},
            "model_parameters": {},
        }
        # Initaialize run parameters
        self.aggregator = aggregator

        self.actuation_enabled = False
        self.actuation_disabled = False
        self.current_datetime = None
        self.current_schedule = None
        self.current_hour = None
        self.current_price = None
        self.actuation_obj = None
        self.flexibility = None
        self.ct_flexibility = None
        self.off_setpoint = None
        self.occupied = False
        self.mapped = None
        self.cleared_prices = []
        self.price_info = []
        self.input_topics = set()

        self.commodity = "electricity"
        self.update_flag = []
        self.demand_curve = []
        self.actuation_price_range = None
        self.prices = []
        self.default_min_price = 0.01
        self.default_max_price = 0.1
        self.market_list = []
        self.market_manager_list = []
        self.market_type = None
        self.day_ahead_market = None
        self.rtp_market = None
        self.oat_predictions = {}

        # Variables declared in configure_main
        self.record_topic = None
        self.market_number = None
        self.single_market_contol_interval = None
        self.inputs = {}
        self.outputs = {}
        self.schedule = {}
        self.actuation_method = None
        self.actuate_onstart = None
        self.input_data_tz = None
        self.actuation_rate = None
        self.actuate_topic = None
        self.price_manager = None
        if config:
            default_config.update(config)
            self.default_config = default_config
        else:
            self.default_config = default_config
        if self.aggregator is None:
            self.vip.config.set_default("config", self.default_config)
            self.vip.config.subscribe(self.configure_main,
                                      actions=["NEW", "UPDATE"],
                                      pattern="config")

    def configure_main(self, config_name, action, contents, **kwargs):
        config = self.default_config.copy()
        config.update(contents)
        _log.debug("Update agent %s configuration -- config --  %s", self.core.identity, config)
        if action == "NEW" or "UPDATE":
            price_multiplier = config.get("price_multiplier", 1.0)
            self.price_manager = MessageManager(self, price_multiplier)

            campus = config.get("campus", "")
            building = config.get("building", "")
            device = config.get("device", "")
            subdevice = config.get("subdevice", "")

            base_record_list = ["tnc", campus, building, device, subdevice]
            base_record_list = list(filter(lambda a: a != "", base_record_list))
            self.record_topic = '/'.join(base_record_list)

            self.actuate_onstart = config.get("actuation_enabled_onstart", True)
            self.actuation_disabled = True if not self.actuate_onstart else False
            self.actuation_method = config.get("actuation_method")
            self.actuation_rate = config.get("control_interval")
            actuate_topic = config.get("actuation_enable_topic", "default")
            if actuate_topic == "default":
                base_record_list.append('actuate')
                self.actuate_topic = '/'.join(base_record_list)
            else:
                self.actuate_topic = actuate_topic

            input_data_tz = config.get("input_data_timezone")
            self.input_data_tz = dateutil.tz.gettz(input_data_tz)
            inputs = config.get("inputs", [])
            schedule = config.get("schedule")
            self.clear_input_subscriptions()
            self.input_topics = set()
            self.init_inputs(inputs)
            self.init_schedule(schedule)
            outputs = config.get("outputs")
            self.init_outputs(outputs)
            self.init_actuation_state(self.actuate_topic, self.actuate_onstart)
            self.init_input_subscriptions()
            market_name = config.get("market_name", "electric")
            self.market_type = config.get("market_type", "tns")
            tns = False if self.market_type != "tns" else True
            #  VOLTTRON MarketService does not allow "leaving"
            #  markets.  Market participants can choose not to participate
            #  in the market process by sending False during the reservation
            #  phase.  This means that once the markets in market_name are
            #  joined the deployment can only be changed from an TNS market
            #  to single time step market by rebuilding both the agent
            #  and the VOLTTRON MarketService.
            _log.debug("CREATE MODEL")
            model_config = config.get("model_parameters", {})
            Model.__init__(self, model_config, **kwargs)
            if not self.market_list and tns is not None and self.model is not None:
                if self.aggregator is None:
                    _log.debug("%s is a transactive agent.", self.core.identity)
                    for i in range(24):
                        self.market_list.append('_'.join([market_name, str(i)]))
                    if tns:
                        rtp_market_list = ["_".join(["refinement", market_name])]
                        self.day_ahead_market = DayAheadMarket(self.outputs, self.market_list, self, self.price_manager)
                        self.rtp_market = RealTimeMarket(self.outputs, rtp_market_list, self, self.price_manager)
                        self.market_manager_list = [self.day_ahead_market, self.rtp_market]
                    else:
                        market_list = ["_".join(["refinement", market_name])]
                        self.rtp_market = RealTimeMarket(self.outputs, market_list, self, self.price_manager)
                        self.single_market_contol_interval = config.get("single_market_control_interval", 15)
                        self.market_manager_list = [self.rtp_market]
                    self.setup()

    def setup(self, **kwargs):
        """
        On start.
        :param sender:
        :param kwargs:
        :return:
        """
        for market in self.market_manager_list:
            market.init_markets()

        if self.market_type == "rtp":
            self.update_prices = self.price_manager.update_rtp_prices
        else:
            self.update_prices = self.price_manager.update_prices

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/start_new_cycle',
                                  callback=self.update_prices)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='tnc/cleared_prices',
                                  callback=self.price_manager.update_cleared_prices)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix="/".join([self.record_topic,
                                                   "update_model"]),
                                  callback=self.update_model)

    def init_inputs(self, inputs):
        for input_info in inputs:
            try:
                point = input_info["point"]
                mapped = input_info["mapped"]
                topic = input_info["topic"]
            except KeyError as ex:
                _log.error("Exception on init_inputs %s", ex)
                sys.exit()

            value = input_info.get("initial_value")
            self.inputs[mapped] = {point: value}
            self.input_topics.add(topic)

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
            # TODO: Update release value anytime agent has state transition for actuation_enable
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
            ct_flex, flex = self.set_control(ct_flex, flex)
            self.ct_flexibility = ct_flex
            fallback = output_info.get("fallback", mean(ct_flex))
            # TODO:  Use condition to determine multiple output scenario
            condition = output_info.get("condition", True)

            try:
                value = self.vip.rpc.call(actuator,
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

    def set_control(self, ct_flex, flex):
        ct_flex = np.linspace(ct_flex[0], ct_flex[1], 11)
        flex = np.linspace(flex[0], flex[1], 11)
        return ct_flex, flex

    def init_input_subscriptions(self):
        """
        Create topic subscriptions for devices.
        :return:
        """
        for topic in self.input_topics:
            _log.debug('Subscribing to: ' + topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                      callback=self.update_input_data)

    def clear_input_subscriptions(self):
        """
        Create topic subscriptions for devices.
        :return:
        """
        for topic in self.input_topics:
            _log.debug('Unubscribing to: ' + topic)
            self.vip.pubsub.unsubscribe(peer='pubsub',
                                        prefix=topic,
                                        callback=self.update_input_data)

    def init_schedule(self, schedule):
        """
        Parse schedule for use in determining occupancy.
        :param schedule:
        :return:
        """
        if schedule:
            for day_str, schedule_info in schedule.items():
                _day = parse(day_str).weekday()
                if schedule_info not in ["always_on", "always_off"]:
                    start = parse(schedule_info["start"]).time()
                    end = parse(schedule_info["end"]).time()
                    self.schedule[_day] = {"start": start, "end": end}
                else:
                    self.schedule[_day] = schedule_info
        else:
            self.occupied = True

    def init_actuation_state(self, actuate_topic, actuate_onstart):
        """
        On-start initialize the actuation state of agent.  Create subscription to
        allow for dynamically disabling/enabling actuation for agent.
        :param actuate_topic:
        :param actuate_onstart:
        :return:
        """
        if self.outputs:
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=actuate_topic,
                                      callback=self.update_actuation_state)
            if actuate_onstart:
                self.update_actuation_state(None, None, None, None, None, True)
        else:
            _log.info("%s - cannot initialize actuation state, "
                      "no configured outputs.", self.core.identity)

    def check_schedule(self, dt):
        if self.actuation_disabled:
            _log.debug("Actuation is disabled!")
            return
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
        if _start <= self.current_datetime.time() < _end:
            self.occupied = True
            if not self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, True)
        else:
            self.occupied = False
            if self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, False)

    def update_actuation_state(self, peer, sender, bus, topic, headers, message):
        state = message
        if sender is not None:
            _log.debug("%s actuation disabled %s",
                       self.core.identity, not bool(state))
            if self.actuation_disabled and not (bool(state)):
                return
            self.actuation_disabled = not bool(state)

        _log.debug("update actuation state : %s with method - %s", state, self.actuation_method)
        if self.actuation_enabled and not bool(state):
            for output_info in list(self.outputs.values()):
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
                if release is not None:
                    try:
                        release_value = self.vip.rpc.call(actuator,
                                                          'get_point',
                                                          topic).get(timeout=10)
                    except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
                        _log.warning("Failed to get {} - ex: {}".format(topic, str(ex)))
                        release_value = None
                else:
                    release_value = None
                self.outputs[name]["release"] = release_value
            if self.actuation_method == "periodic":
                _log.debug("Setup periodic actuation: %s -- %s", self.core.identity, self.actuation_rate)
                self.actuation_obj = self.core.periodic(self.actuation_rate, self.do_actuation, wait=self.actuation_rate)
        self.actuation_enabled = state

    def update_outputs(self, name, price):
        _log.debug("update_outputs: %s", self.core.identity)
        if price is None:
            price = self.price_manager.get_current_cleared_price(self.get_current_datetime())
            if price is None:
                return
        sets = self.outputs[name]["ct_flex"]
        prices = self.price_manager.get_price_array(self.get_current_datetime())
        _log.debug("Call determine_control: %s", self.core.identity)
        value = self.determine_control(sets, prices, price)
        _log.debug("determine_control for time: %s -  price: %s - price_range: %s - control: %s",
                   format_timestamp(self.get_current_datetime()), price, prices, value)
        self.outputs[name]["value"] = value
        point = self.outputs.get("point", name)
        topic_suffix = "Actuate"
        message = {point: value, "Price": price}
        self.publish_record(topic_suffix, message)

    def do_actuation(self, price=None):
        _log.debug("do_actuation {}".format(self.outputs))
        for name, output_info in self.outputs.items():
            if not output_info["condition"]:
                continue
            _log.debug("call update_outputs - %s", self.core.identity)
            self.update_outputs(name, price)
            topic = output_info["topic"]
            point = output_info["point"]
            actuator = output_info["actuator"]
            value = output_info.get("value")
            offset = output_info["offset"]
            if value is not None and self.occupied:
                _log.debug("ACTUATE: %s -- %s", self.occupied, value)
                value = value + offset
                self.actuate(topic, value, actuator)

    def actuate(self, point_topic, value, actuator):
        try:
            self.vip.rpc.call(actuator,
                              'set_point',
                              self.core.identity,
                              point_topic,
                              value).get(timeout=15)
        except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
            _log.warning("Failed to set %s - ex: %s", point_topic, str(ex))

    def determine_control(self, sets, prices, price):
        """
        prices is an list of 11 elements, evenly spaced from the smallest price
        to the largest price and corresponds to the y-values of a line.  sets
        is an np.array of 11 elements, evenly spaced from the control value at
        the lowest price to the control value at the highest price and
        corresponds to the x-values of a line.  Price is the cleared price.
        :param sets: np.array;
        :param prices: list;
        :param price: float
        :return:
        """
        _log.debug("determine_control - transactive.py: %s", self.core.identity)
        control = np.interp(price, prices, sets)
        control = self.clamp(control, min(self.ct_flexibility), max(self.ct_flexibility))
        return control

    def update_input_data(self, peer, sender, bus, topic, headers, message):
        """
        Call back method for data subscription for
        device data from MasterDriverAgent or building simulation.
        :param peer:
        :param sender:
        :param bus:
        :param topic: str; topic for device - devices/campus/building/device/all
        :param headers: dict; contains Date/Timestamp
        :param message: list of dicts of key value pairs; [{data}, {metadata}]
        :return:
        """
        # data is assumed to be in format from VOLTTRON master driver.
        data = message[0]
        try:
            current_datetime = parse(headers.get("Date"))
        except TypeError:
            _log.debug("%s could not parse Datetime in input data payload!",
                       self.core.identity)
            current_datetime = None
        if current_datetime is not None:
            self.current_datetime = current_datetime.astimezone(self.input_data_tz)
        self.update_data(data)
        if current_datetime is not None and self.schedule:
            self.check_schedule(current_datetime)

    def update_data(self, data):
        """
        Each time data comes in on message bus from MasterDriverAgent
        update the data for access by model.
        :param data: dict; key value pairs from master driver.
        :return:
        """
        to_publish = {}
        for name, input_data in self.inputs.items():
            for point, value in input_data.items():
                if point in data:
                    self.inputs[name][point] = data[point]
                    to_publish[point] = data[point]
        topic_suffix = "InputData"
        message = to_publish
        self.publish_record(topic_suffix, message)
        # Call models update_data method
        if self.model is not None:
            self.model.update_data()

    def get_input_value(self, mapped):
        """
        Called by model of concrete implementation of transactive to
        obtain the current value for a mapped data point.
        :param mapped:
        :return:
        """
        try:
            return list(self.inputs[mapped].values())[0]
        except KeyError:
            return None

    def update_model(self, peer, sender, bus, topic, headers, message):
        coefficients = message
        if self.model is not None:
            self.model.update_coefficients(coefficients)

    def clamp(self, value, x1, x2):
        min_value = min(abs(x1), abs(x2))
        max_value = max(abs(x1), abs(x2))
        value = value
        return min(max(value, min_value), max_value)

    def publish_record(self, topic_suffix, message):
        headers = {headers_mod.DATE: format_timestamp(get_aware_utc_now())}
        message["TimeStamp"] = format_timestamp(self.get_current_datetime())
        topic = "/".join([self.record_topic, topic_suffix])
        self.vip.pubsub.publish("pubsub", topic, headers, message).get()

    def get_current_datetime(self):
        """
        Current datetime based on input data from
        real building (MasterDriver) or simulation (Typically E+).
        If no inputs are configured or no data has been ingested return
        utc now time.
        :return: tz aware datetime.
        """
        if self.current_datetime is not None:
            return self.current_datetime
        else:
            return dt.now()

    def get_current_output(self):
        output_info = {}
        mapped = ''
        for name, output in self.outputs.items():
            output_info = output
            mapped = name
            if output["condition"]:
                break
        return output_info, mapped

    def update_market_intervals(self, intervals, correction_market):
        if not correction_market:
            if self.day_ahead_market is not None:
                self.day_ahead_market.update_market_intervals(intervals)
        else:
            if self.rtp_market is not None:
                self.rtp_market.update_market_intervals(intervals)


class MessageManager(object):
    def __init__(self, parent, price_multiplier):
        self.market_type = "auction"
        self.parent = parent
        self.price_multiplier = price_multiplier
        self.correction_market = False
        self.cleared_prices = OrderedDict()
        self.price_info = OrderedDict()
        self.default_min_price = 0.035
        self.default_max_price = 0.07
        self.run_dayahead_market = False

    def update_prices(self, peer, sender, bus, topic, headers, message):
        raw_price_info = message["price_info"]
        raw_initial_prices = message["prices"]
        oat_predictions = message.get("temp", [])
        correction_market = message.get("correction_market", False)
        market_intervals = message.get("market_intervals")
        _log.debug("Update prices price: {} - for interval: {}".format(raw_initial_prices, market_intervals))
        self.parent.update_market_intervals(market_intervals, correction_market)
        price_info = lists_to_dict(market_intervals, raw_price_info)
        initial_prices = lists_to_dict(market_intervals, raw_initial_prices)
        if oat_predictions:
            self.parent.oat_predictions = lists_to_dict(market_intervals, oat_predictions)
            _log.debug("OAT predictions: %s", self.parent.oat_predictions)
        for market_time in market_intervals:
            avg_price, stdev_price = price_info[market_time]
            hour_of_year = calculate_hour_of_year(market_time)
            price_array = self.determine_prices(avg_price, stdev_price)
            self.price_info[hour_of_year] = price_array
            self.cleared_prices[hour_of_year] = initial_prices[market_time]

        self.correction_market = correction_market
        if not correction_market:
            self.run_dayahead_market = True
        else:
            self.run_dayahead_market = False

    def update_cleared_prices(self, peer, sender, bus, topic, headers, message):
        correction_market = message.get("correction_market", False)
        raw_price_info = message["price_info"]
        raw_cleared_prices = message["prices"]
        market_intervals = message.get("market_intervals")
        _log.debug("Update cleared price: {} - for interval: {}".format(raw_cleared_prices, market_intervals))
        self.parent.update_market_intervals(market_intervals, correction_market)
        market_intervals = [interval for interval in market_intervals]
        cleared_prices = lists_to_dict(market_intervals, raw_cleared_prices)
        price_info = lists_to_dict(market_intervals, raw_price_info)
        for market_time in market_intervals:
            hour_of_year = calculate_hour_of_year(market_time)
            avg_price, stdev_price = price_info[market_time]
            price_array = self.determine_prices(avg_price, stdev_price)
            self.price_info[hour_of_year] = price_array
            self.cleared_prices[hour_of_year] = cleared_prices[market_time]
        self.prune_data()

    def update_rtp_prices(self, peer, sender, bus, topic, headers, message):
        market_prices = message["prices"]
        _log.debug("Get RTP Prices: {}".format(market_prices))
        hour_of_year = calculate_hour_of_year(dt.now())
        self.parent.update_market_intervals([str(dt.now())], True)
        self.cleared_prices[hour_of_year] = market_prices[-1]
        price_array = self.determine_prices(None, None, price_array=market_prices)
        self.price_info[hour_of_year] = price_array
        self.prune_data()

    def determine_prices(self, avg_price, stdev_price, price_array=None):
        """
        Determine minimum and maximum price from 24-hour look ahead prices.  If the TNS
        market architecture is not utilized, this function must be overwritten in the child class.
        :return:
        """
        try:
            if price_array is None:
                price_min = avg_price - self.price_multiplier * stdev_price
                price_max = avg_price + self.price_multiplier * stdev_price
            else:
                avg_price = np.mean(price_array)
                stdev_price = np.std(price_array)
                price_min = avg_price - self.price_multiplier * stdev_price
                price_max = avg_price + self.price_multiplier * stdev_price
        except:
            avg_price = None
            stdev_price = None
            price_min = self.default_min_price
            price_max = self.default_max_price
        _log.debug("Prices: {} - avg: {} - std: {}".format(price_array, avg_price, stdev_price))
        price_array = np.linspace(price_min, price_max, 11)
        return price_array

    def prune_data(self):
        for k in range(len(self.cleared_prices) - 48):
            self.cleared_prices.popitem(last=False)
        for k in range(len(self.price_info) - 48):
            self.price_info.popitem(last=False)

    def get_current_cleared_price(self, _dt):
        hour_of_year = calculate_hour_of_year(_dt)
        if hour_of_year in self.cleared_prices:
            price = self.cleared_prices[hour_of_year]
        else:
            _log.debug("No cleared price for current hour!")
            price = None
        return price

    def get_price_array(self, _dt):
        hour_of_year = calculate_hour_of_year(_dt)
        if hour_of_year in self.price_info:
            price_array = self.price_info[hour_of_year]
        else:
            _log.debug("No price array for current hour!")
            price_array = None
        return price_array
