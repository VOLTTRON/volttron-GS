import logging
from datetime import timedelta as td
import numpy as np

from dateutil.parser import parse
import dateutil.tz
import gevent
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

_log = logging.getLogger(__name__)
setup_logging()
__version__ = '0.3'


class TransactiveBase(MarketAgent):
    def __init__(self, config, **kwargs):
        super(TransactiveBase, self).__init__(**kwargs)

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
        self.oat_predictions = []
        self.market_prices = {}
        self.day_ahead_prices = []
        self.input_topics = []
        self.inputs = {}
        self.outputs = {}
        self.schedule = {}
        self.commodity = "Electricity"

        campus = config.get("campus", "")
        building = config.get("building", "")
        base_record_list = ["tnc", campus, building]
        base_record_list = list(filter(lambda a: a != "", base_record_list))
        self.record_topic = '/'.join(base_record_list)
        # set actuation parameters for device control
        actuate_topic = config.get("actuation_enable_topic", "default")
        if actuate_topic == "default":
            self.actuate_topic = '/'.join([campus, building, 'actuate'])
        else:
            self.actuate_topic = actuate_topic
        self.actuate_onstart = config.get("actuation_enabled_onstart", False)
        self.actuation_method = config.get("actuation_method", "periodic")
        self.actuation_rate = config.get("control_interval", 300)

        self.price_multiplier = config.get("price_multiplier", 1.0)
        self.default_min_price = 0.01
        self.default_max_price = 0.1
        self.default_price = config.get("fallback_price", 0.05)
        input_data_tz = config.get("input_data_timezone", "UTC")
        self.input_data_tz = dateutil.tz.gettz(input_data_tz)
        inputs = config.get("inputs", [])
        self._outputs = config.get("outputs", [])
        schedule = config.get("schedule", {})

        self.init_inputs(inputs)
        self.init_schedule(schedule)
        market_name = config.get("market_name", "electric")

        tns_integration = config.get("tns", True)
        if tns_integration:
            self.market_number = 24
            self.single_market_contol_interval = None
        else:
            self.market_number = 1
            self.single_market_contol_interval = config.get("single_market_contol_interval", 15)

        self.market_name = []
        for i in range(self.market_number):
            self.market_name.append('_'.join([market_name, str(i)]))

        self.update_flag = []
        self.demand_curve = []
        self.actuation_price_range = None
        self.prices = []

    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        """
        On start.
        :param sender:
        :param kwargs:
        :return:
        """
        self.init_outputs(self._outputs)
        self.init_actuation_state(self.actuate_topic, self.actuate_onstart)
        self.init_input_subscriptions()
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/start_new_cycle',
                                  callback=self.update_prices)

    def init_markets(self):
        for market in self.market_name:
            self.join_market(market, BUYER, None, self.offer_callback,
                             None, self.price_callback, self.error_callback)
            self.update_flag.append(False)
            self.demand_curve.append(PolyLine())

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
            ct_flex, flex = self.set_control(ct_flex, flex)

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
        for topic in self.input_topics:
            _log.debug('Subscribing to: ' + topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                      callback=self.update_input_data)

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

    def init_actuation_state(self, actuate_topic, actuate_onstart):
        if self._outputs:
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=actuate_topic,
                                      callback=self.update_actuation_state)
            if actuate_onstart:
                self.update_actuation_state(None, None, None, None, None, True)
                self.actuation_disabled = False
        else:
            _log.info("{} - cannot initialize actuation state, no configured outputs.".format(self.agent_name))

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
                        release_value = self.vip.rpc.call(actuator,
                                                          'get_point',
                                                          topic).get(timeout=10)
                    except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
                        _log.warning("Failed to get {} - ex: {}".format(topic, str(ex)))
                else:
                    release_value = None
                self.outputs[name]["release"] = release_value
            if self.actuation_method == "periodic":
                self.actuation_obj = self.core.periodic(self.actuation_rate, self.do_actuation, wait=self.actuation_rate)
        self.actuation_enabled = state

    def update_outputs(self, name, price):
        if price is None:
            if self.current_price is None:
                return
            price = self.current_price
        sets = self.outputs[name]["ct_flex"]
        if self.actuation_price_range is not None:
            prices = self.actuation_price_range
        else:
            prices = self.determine_prices()
        value = self.determine_control(sets, prices, price)
        self.outputs[name]["value"] = value
        point = self.outputs.get("point", name)
        topic_suffix = "/".join([self.agent_name, "Actuate"])
        message = {point: value, "Price": price}
        self.publish_record(topic_suffix, message)

    def do_actuation(self, price=None):
        _log.debug("actuation {}".format(self.outputs))
        for name, output_info in self.outputs.items():
            if not output_info["condition"]:
                continue
            self.update_outputs(name, price)
            topic = output_info["topic"]
            point = output_info["point"]
            actuator = output_info["actuator"]
            value = output_info.get("value")
            offset = output_info["offset"]
            if value is not None:
                value = value + offset
                self.actuate(topic, value, actuator)

    def actuate(self, point_topic, value, actuator):
        try:
            self.vip.rpc.call(actuator,
                              'set_point',
                              self.agent_name,
                              point_topic,
                              value).get(timeout=10)
        except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
            _log.warning("Failed to set {} - ex: {}".format(point_topic, str(ex)))

    def offer_callback(self, timestamp, market_name, buyer_seller):
        for name, output in self.outputs.items():
            output_info = output
            self.mapped = name
            if output["condition"]:
                break
        self.flexibility = output_info["flex"]
        self.ct_flexibility = output_info["ct_flex"]
        self.off_setpoint = output_info["off_setpoint"]
        market_index = self.market_name.index(market_name)
        if market_index > 0:
            while not self.update_flag[market_index - 1]:
                gevent.sleep(1)
        if market_index == len(self.market_name) - 1:
            for i in range(len(self.market_name)):
                self.update_flag[i] = False
        if market_index == 0 and self.current_datetime is not None:
            self.init_predictions(output_info)

        sched_index = self.determine_sched_index(market_index)
        market_time = self.current_datetime + td(hours=market_index + 1)
        occupied = self.check_future_schedule(market_time)

        demand_curve = self.create_demand_curve(market_index, sched_index, occupied)
        self.demand_curve[market_index] = demand_curve
        result, message = self.make_offer(market_name, buyer_seller, demand_curve)

    def create_demand_curve(self, market_index, sched_index, occupied):
        _log.debug("{} debug demand_curve - index: {} - sched: {}".format(self.agent_name,
                                                                          market_index,
                                                                          sched_index))
        demand_curve = PolyLine()
        prices = self.determine_prices()
        ct_flx = []
        for i in range(len(prices)):
            if occupied:
                _set = self.ct_flexibility[i]
            else:
                _set = self.off_setpoint
            ct_flx.append(_set)
            q = self.get_q(_set, sched_index, market_index, occupied)
            demand_curve.add(Point(price=prices[i], quantity=q))

        ct_flx = [min(ct_flx), max(ct_flx)] if ct_flx else []
        topic_suffix = "/".join([self.agent_name, "DemandCurve"])
        message = {"MarketIndex": market_index, "Curve": demand_curve.tuppleize(), "Commodity": self.commodity}
        _log.debug("{} debug demand_curve - curve: {}".format(self.agent_name, demand_curve.points))
        self.publish_record(topic_suffix, message)
        return demand_curve

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        market_index = self.market_name.index(market_name)
        if price is None:
            if self.market_prices:
                try:
                    price = self.market_prices[market_index]
                    _log.warn("{} - market {} did not clear, using market_prices!".format(self.agent_name, market_name))
                except IndexError:
                    _log.warn("{} - market {} did not clear, and exception was raised when accessing market_prices!".format(self.agent_name, market_name))
                    price = self.default_price
            else:
                _log.warn("{} - market {} did not clear, and no market_prices, using default fallback price!".format(self.agent_name, market_name))
                price = self.default_price
        if self.demand_curve[market_index] is not None and self.demand_curve[market_index].points:
            cleared_quantity = self.demand_curve[market_index].x(price)

        sched_index = self.determine_sched_index(market_index)
        _log.debug("{} price callback market: {}, price: {}, quantity: {}".format(self.agent_name, market_name, price, quantity))
        topic_suffix = "/".join([self.agent_name, "MarketClear"])
        message = {"MarketIndex": market_index, "Price": price, "Quantity": [quantity, cleared_quantity], "Commodity": self.commodity}
        self.publish_record(topic_suffix, message)
        # this line of logic was different in VAV agent
        # if price is not None:
        #if price is not None and market_index < self.market_number-1:
        if price is not None:
            self.update_state(market_index, sched_index, price)
        if price is not None and self.actuation_method == "market_clear" and market_index == 0:
            self.do_actuation(price)

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        _log.debug('{} - error for Market: {} {}, Message: {}'.format(self.agent_name,
                                                                      market_name,
                                                                      buyer_seller,
                                                                      aux))

    def update_prices(self, peer, sender, bus, topic, headers, message):
        _log.debug("Get prices prior to market start.")
        current_date = parse(message['Date']) + td(hours=1)
        current_hour = parse(message['Date']).hour
        if self.market_prices:
            market_prices_start_date = self.market_prices.keys()[0]
            if current_date - market_prices_start_date > td(hours=24, minutes=50):
                prices = self.market_prices.values()[0]
                prices.pop(0)
                prices.append(self.current_price)
                self.market_prices = {}
                new_start_date = market_prices_start_date + td(hours=1)
                self.market_prices[new_start_date] = prices
        else:
            self.market_prices[current_date] = message['prices']

        # Store received prices so we can use it later when doing clearing process
        if self.day_ahead_prices:
            self.actuation_price_range = self.determine_prices()
            if current_hour != self.current_hour:
                self.current_price = self.day_ahead_prices[0]
        self.current_hour = current_hour
        self.oat_predictions = []
        oat_predictions = message.get("temp", [])

        self.oat_predictions = oat_predictions
        self.day_ahead_prices = message['prices']  # Array of prices

    def determine_control(self, sets, prices, price):
        control = np.interp(price, prices, sets)
        control = self.clamp(control, min(self.ct_flexibility), max(self.ct_flexibility))
        return control

    def determine_prices(self):
        """
        Determine minimum and maximum price from 24-hour look ahead prices.  If the TNS
        market architecture is not utilized, this function must be overwritten in the child class.
        :return:
        """
        if self.market_prices:
            avg_price = np.mean(self.market_prices.values()[0])
            std_price = np.std(self.market_prices.values()[0])
            price_min = avg_price - self.price_multiplier * std_price
            price_max = avg_price + self.price_multiplier * std_price
        else:
            avg_price = None
            std_price = None
            price_min = self.default_min_price
            price_max = self.default_max_price
        _log.debug("Prices: {} - avg: {} - std: {}".format(self.market_prices, avg_price, std_price))
        price_array = np.linspace(price_min, price_max, 11)
        return price_array

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

    def clamp(self, value, x1, x2):
        min_value = min(abs(x1), abs(x2))
        max_value = max(abs(x1), abs(x2))
        value = value
        return min(max(value, min_value), max_value)

    def publish_record(self, topic_suffix, message):
        headers = {headers_mod.DATE: format_timestamp(get_aware_utc_now())}
        message["TimeStamp"] = format_timestamp(self.current_datetime)
        topic = "/".join([self.record_topic, topic_suffix])
        self.vip.pubsub.publish("pubsub", topic, headers, message).get()
