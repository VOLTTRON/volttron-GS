import logging

from volttron.pnnl.transactive_base.transactive.transactive import TransactiveBase
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
from volttron.platform.agent.utils import setup_logging

_log = logging.getLogger(__name__)
setup_logging()
__version__ = '0.3'


class Aggregator(TransactiveBase):
    def __init__(self, config, **kwargs):
        super(Aggregator, self).__init__(config, **kwargs)
        supplier_market_base_name = config.get("supplier_market_name", "")
        consumer_market_base_name = config.get("consumer_market_name", [])

        if isinstance(consumer_market_base_name, str):
            consumer_market_base_name = [consumer_market_base_name]

        self.aggregate_clearing_market = config.get("aggregate_clearing_market", "electric")
        self.supply_commodity = None
        self.consumer_commodity = self.commodity

        self.consumer_demand_curve = dict.fromkeys(consumer_market_base_name, [])
        self.consumer_market = dict.fromkeys(consumer_market_base_name, [])
        self.supplier_market = []
        self.supplier_market = ['_'.join([supplier_market_base_name, str(i)]) for i in range(self.market_number)]
        self.aggregate_demand = [None]*self.market_number
        if consumer_market_base_name:
            for market_name in self.consumer_market:
                self.consumer_market[market_name] = ['_'.join([market_name, str(i)]) for i in range(self.market_number)]
                self.consumer_demand_curve[market_name] = [None]*self.market_number
                self.consumer_reserve_demand_curve[market_name] = [None]*self.market_number
        self.supplier_curve = []

    def init_markets(self):
        for market in self.supplier_market:
            self.join_market(market, SELLER, None, None,
                             self.aggregate_callback, self.supplier_price_callback, self.error_callback)
            self.supplier_curve.append(None)
        for market_base, market_list in self.consumer_market.items():
            for market in market_list:
                self.join_market(market, BUYER, None, None,
                                 None, self.consumer_price_callback, self.error_callback)

    def aggregate_callback(self, timestamp, market_name, buyer_seller, agg_demand):
        if buyer_seller == BUYER:
            market_index = self.supplier_market.index(market_name)
            _log.debug("{} - received aggregated {} curve - {}".format(self.agent_name, market_name, agg_demand.points))
            self.aggregate_demand[market_index] = agg_demand
            self.translate_aggregate_demand(agg_demand, market_index)

            if self.consumer_market:
                for market_base, market_list in self.consumer_market.items():
                    success, message = self.make_offer(market_list[market_index], BUYER, self.consumer_demand_curve[market_base][market_index])

                    # Database code for data analysis
                    topic_suffix = "/".join([self.agent_name, "DemandCurve"])
                    message = {
                        "MarketIndex": market_index,
                        "Curve": self.consumer_demand_curve[market_base][market_index].tuppleize(),
                        "Commodity": market_base
                    }
                    if self.consumer_reserve_demand_curve[market_base][market_index]:
                        message['Reserve_Curve'] = self.consumer_reserve_demand_curve[market_base][market_index].tuppleize()
                    _log.debug("{} debug demand_curve - curve: {}".format(self.agent_name,
                                                                          self.consumer_demand_curve[market_base][market_index].points))
                    self.publish_record(topic_suffix, message)
            elif self.supplier_market:
                success, message = self.make_offer(self.supplier_market[market_index], SELLER, self.supplier_curve[market_index])
            else:
                _log.warn("{} - No markets to submit supply curve!".format(self.agent_name))
                success = False

            if success:
                _log.debug("{}: make a offer for {}".format(self.agent_name, market_name))
            else:
                _log.debug("{}: offer for the {} was rejected".format(self.agent_name, market_name))

    def consumer_price_callback(self, timestamp, consumer_market, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, consumer_market, price, quantity, timestamp)
        for market_base, market_list in self.consumer_market.items():
            if consumer_market in market_list:
                market_index = market_list.index(consumer_market)
                if market_base == self.aggregate_clearing_market:
                    supply_market = self.supplier_market[market_index]
                    if price is not None:
                        self.make_supply_offer(price, supply_market)
                    if self.consumer_demand_curve[market_base][market_index] is not None and self.consumer_demand_curve[market_base][market_index]:
                        cleared_quantity = self.consumer_demand_curve[market_base][market_index].x(price)
                        _log.debug("{} price callback market: {}, price: {}, quantity: {}".format(self.agent_name, consumer_market, price, quantity))
                        topic_suffix = "/".join([self.agent_name, "MarketClear"])
                        message = {"MarketIndex": market_index, "Price": price, "Quantity": [quantity, cleared_quantity], "Commodity": market_base}
                        self.publish_record(topic_suffix, message)

    def create_supply_curve(self, clear_price, supply_market):
        index = self.supplier_market.index(supply_market)
        supply_curve = PolyLine()
        try:
            if self.aggregate_demand:
                min_quantity = self.aggregate_demand[index].min_x()*0.8
                max_quantity = self.aggregate_demand[index].max_x()*1.2
            else:
                min_quantity = 0.0
                max_quantity = 10000.0
        except:
            min_quantity = 0.0
            max_quantity = 10000.0
        supply_curve.add(Point(price=clear_price, quantity=min_quantity))
        supply_curve.add(Point(price=clear_price, quantity=max_quantity))
        return supply_curve

    def supplier_price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, market_name, price, quantity, timestamp)

    def make_supply_offer(self, price, supply_market):
        supply_curve = self.create_supply_curve(price, supply_market)
        success, message = self.make_offer(supply_market, SELLER, supply_curve)
        if success:
            _log.debug("{}: make offer for Market: {} {} Curve: {}".format(self.agent_name,
                                                                           supply_market,
                                                                           SELLER,
                                                                           supply_curve.points))
        market_index = self.supplier_market.index(supply_market)
        topic_suffix = "/".join([self.agent_name, "SupplyCurve"])
        message = {"MarketIndex": market_index, "Curve": supply_curve.tuppleize(), "Commodity": self.supply_commodity}
        _log.debug("{} debug demand_curve - curve: {}".format(self.agent_name, supply_curve.points))
        self.publish_record(topic_suffix, message)

    def report_cleared_price(self, buyer_seller, market_name, price, quantity, timestamp):
        _log.debug("{}: ts - {}, Market - {} as {}, Price - {} Quantity - {}".format(self.agent_name,
                                                                                     timestamp,
                                                                                     market_name,
                                                                                     buyer_seller,
                                                                                     price,
                                                                                     quantity))

    def offer_callback(self, timestamp, market_name, buyer_seller):
        pass