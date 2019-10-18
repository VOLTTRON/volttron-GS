import logging
from datetime import timedelta as td
import numpy as np
import gevent
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.utils import setup_logging, format_timestamp, get_aware_utc_now
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.messaging import topics, headers as headers_mod
from .device_control_base import DeviceControlBase

_log = logging.getLogger(__name__)
setup_logging()
__version__ = '0.3'


class TransactiveBase(MarketAgent):
    def __init__(self, config, **kwargs):
        super(TransactiveBase, self).__init__(**kwargs)
        self.current_hour = None
        self.current_price = None
        self.flexibility = None
        self.ct_flexibility = None
        self.off_setpoint = None
        self.occupied = False
        self.mapped = None
        self.oat_predictions = []
        self.market_prices = []
        self.commodity = "Electricity"

        self.price_multiplier = config.get("price_multiplier", 1.0)
        self.default_min_price = 0.01
        self.default_max_price = 0.1
        self.default_price = config.get("fallback_price", 0.05)

        market_name = config.get("market_name", "electric")

        tns_integration = config.get("tns", True)
        campus = config.get("campus", "")
        building = config.get("building", "")
        self.record_topic = '/'.join(["tnc", campus, building])
        self.device_control = DeviceControlBase(config, self.vip, self.record_topic)

        if tns_integration:
            self.market_number = 24
            self.single_market_control_interval = None
        else:
            self.market_number = 1
            self.single_market_control_interval = config.get("single_market_contol_interval", 15)

        self.market_name = []
        for i in range(self.market_number):
            self.market_name.append('_'.join([market_name, str(i)]))

        self.update_flag = []
        self.prices = []
        self.demand_curve = []
        self.actuation_rate = config.get("control_interval", 300)
        if self.actuation_method == "periodic":
            self.actuation_obj = self.core.periodic(self.actuation_rate,
                                                        self.do_actuation,
                                                        wait=self.actuation_rate)

    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        """
        On start.
        :param sender:
        :param kwargs:
        :return:
        """
        self.device_control.init_outputs(self._outputs)
        self.device_control.init_actuation_state(self.actuate_topic, self.actuate_onstart)
        self.device_control.input_subscriptions()
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/start_new_cycle',
                                  callback=self.update_prices)

    def init_markets(self):
        for market in self.market_name:
            self.join_market(market, BUYER, None, self.offer_callback,
                             None, self.price_callback, self.error_callback)
            self.update_flag.append(False)
            self.demand_curve.append(PolyLine())


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

        sched_index = self.device_control.determine_sched_index(market_index)
        market_time = self.current_datetime + td(hours=market_index + 1)
        occupied = self.device_control.check_future_schedule(market_time)

        demand_curve = self.create_demand_curve(market_index, sched_index, occupied)
        self.demand_curve[market_index] = demand_curve
        result, message = self.make_offer(market_name, buyer_seller, demand_curve)

    def create_demand_curve(self, market_index, sched_index, occupied):
        _log.debug("{} debug demand_curve - index: {} - sched: {}".format(self.agent_name,
                                                                          market_index,
                                                                          sched_index))
        demand_curve = PolyLine()
        reserve_demand_curve = PolyLine()
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
        message = {"MarketIndex": market_index,
                   "Curve": demand_curve.tuppleize(),
                   "Commodity": self.commodity}
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
        current_hour = message['hour']

        # Store received prices so we can use it later when doing clearing process
        if self.market_prices:
            if current_hour != self.current_hour:
                self.current_price = self.market_prices[0]
        self.current_hour = current_hour
        self.oat_predictions = []
        oat_predictions = message.get("temp", [])

        self.oat_predictions = oat_predictions
        self.market_prices = message['prices']  # Array of prices

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
            avg_price = mean(self.market_prices)
            std_price = stdev(self.market_prices)
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

    def clamp(self, value, x1, x2):
        min_value = min(abs(x1), abs(x2))
        max_value = max(abs(x1), abs(x2))
        value = value
        return min(max(value, min_value), max_value)

    def do_actuation(self, price=None):
        _log.debug("actuation {}".format(self.device_control.outputs))
        for name, output_info in self.device_control.outputs.items():
            if not output_info["condition"]:
                continue
            control_value = self.update_outputs(name, price)
            output_info["value"] = control_value
            if control_value is not None:
                self.device_control.actuate(output_info)

    def update_outputs(self, name, price):
        if price is None:
            if self.current_price is None:
                return
            price = self.current_price
        sets = self.device_control.outputs[name]["ct_flex"]
        prices = self.determine_prices()
        value = self.determine_control(sets, prices, price)
        point = self.device_control.outputs.get("point", name)
        topic_suffix = "/".join([self.agent_name, "Actuate"])
        message = {point: value, "Price": price}
        self.publish_record(topic_suffix, message)
        return value

    def publish_record(self, topic_suffix, message):
        headers = {headers_mod.DATE: format_timestamp(get_aware_utc_now())}
        message["TimeStamp"] = format_timestamp(self.current_datetime)
        topic = "/".join([self.record_topic, topic_suffix])
        self.vip.pubsub.publish("pubsub", topic, headers, message).get()
