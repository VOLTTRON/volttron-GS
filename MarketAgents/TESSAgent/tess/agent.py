# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2018, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

import sys
import logging
from volttron.platform.agent import utils
from volttron.pnnl.transactive_base.transactive.aggregator_base import Aggregator
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.pnnl.models import Model
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


class TESSAgent(Aggregator, Model):
    """
    The TESS Agent participates in Electricity Market as consumer of electricity at fixed price.
    It participates in internal Chilled Water market as supplier of chilled water at fixed price.
    """

    def __init__(self, config_path, **kwargs):
        try:
            config = utils.load_config(config_path)
        except Exception.StandardError:
            config = {}
        self.agent_name = config.get("agent_name", "tess_agent")
        model_config = config.get("model_parameters", {})
        Aggregator.__init__(self, config, **kwargs)
        Model.__init__(self, model_config, **kwargs)
        self.numHours = 24
        self.cooling_load = [None] * self.numHours
        self.init_markets()
        self.indices = [None] * self.numHours
        self.cooling_load_copy = self.cooling_load[:]

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.debug("TESS onstart")
        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/calculate_demand',
                                  callback=self._calculate_demand)

    def aggregate_callback(self, timestamp, market_name, buyer_seller, agg_demand):
        if buyer_seller == BUYER:
            market_index = self.supplier_market.index(market_name)
            #_log.debug("{} - received aggregated {} curve - {}".format(self.agent_name, market_name, agg_demand.points))
            self.aggregate_demand[market_index] = agg_demand
            success = self.translate_aggregate_demand(agg_demand, market_index)

            if self.consumer_market and success:
                for market_base, market_list in self.consumer_market.items():
                    _log.debug("TESS: market_list: {}".format(market_list))
                    for index in range(0, len(market_list)):
                        if self.consumer_demand_curve[market_base][index] is not None:
                            success, message = self.make_offer(market_list[index], BUYER, self.consumer_demand_curve[market_base][index])

                            # Database code for data analysis
                            topic_suffix = "/".join([self.agent_name, "DemandCurve"])
                            message = {
                                "MarketIndex": market_index,
                                "Curve": self.consumer_demand_curve[market_base][market_index].tuppleize(),
                                "Commodity": market_base
                            }
                            _log.debug("{} debug demand_curve - curve: {}".format(self.agent_name,
                                                                                  self.consumer_demand_curve[market_base][market_index].points))
                            self.publish_record(topic_suffix, message)
            elif self.supplier_market and success:
                #_log.debug("TESS: supplier_market: {}, market_index: {}".format(self.supplier_market, market_index))
                for index in range(0, len(self.supplier_market)):
                    success, message = self.make_offer(self.supplier_market[index], SELLER, self.supplier_curve[market_index])
            else:
                _log.warn("{} - No markets to submit supply curve!".format(self.agent_name))
                success = False

            if success:
                _log.debug("{}: make a offer for {}".format(self.agent_name, market_name))
            else:
                _log.debug("{}: offer for the {} was rejected".format(self.agent_name, market_name))

    def translate_aggregate_demand(self, chilled_water_demand, index):
        _log.debug("TESS: translate_aggregate_demand, chilled_water_demand: {}".format(chilled_water_demand.points))
        #_log.debug("TESS: translate_aggregate_demand, index: {}".format(index))
        _log.debug("TESS: translate_aggregate_demand, oat_predictions: {}".format(self.oat_predictions))
        #_log.debug("TESS: length of chilled_water: {}".format(len(chilled_water_demand.points)))
        # point.x = quantity, point.y = price
        # Assuming points.x is cooling load, points.y is price
        price = self.market_prices[index]
        self.cooling_load[index] = chilled_water_demand.x(price)
        success = None
        self.indices[index] = index
        optimization_ready = all([False if i is None else True for i in self.cooling_load])
        if optimization_ready:
            _log.debug("TESS: market_prices = {}".format(self.market_prices))
            _log.debug("TESS: reserve_market_prices = {}".format(self.reserve_market_prices))
            _log.debug("TESS: oat_predictions = {}".format(self.oat_predictions))
            _log.debug("TESS: cooling_load = {}".format(self.cooling_load))
            T_out = [-0.05 * (t - 14.0) ** 2 + 30.0 for t in range(1, 25)]
            tess_power_inject, tess_power_reserve = self.model.run_tess_optimization(self.market_prices,
                                                                                        self.reserve_market_prices,
                                                                                        self.oat_predictions,
                                                                                        #T_out,
                                                                                        self.cooling_load)
            tess_power_inject = [i*-1 for i in tess_power_inject]
            self.cooling_load_copy = self.cooling_load[:]
            self.cooling_load = [None]*self.numHours
            _log.debug("TESS: translate_aggregate_demand tess_power_inject: {}, tess_power_reserve: {}".format(
                tess_power_inject,
                tess_power_reserve))
            price_min, price_max = self.determine_price_min_max()
            _log.debug("TESS: price_min: {}, price_max: {}".format(price_min, price_max))
            for i in range(0, len(self.market_prices)):
                electric_demand_curve = PolyLine()
                electric_demand_curve.add(Point(tess_power_inject[i], price_min))
                electric_demand_curve.add(Point(tess_power_inject[i], price_max))
                market_base_name = list(self.consumer_demand_curve.keys())
                _log.debug("TESS: MARKET BASE NAME:{0} {1}".format(market_base_name, i))
                self.consumer_demand_curve[market_base_name[0]][i] = electric_demand_curve
                _log.debug("TESS: electric demand : Pt: {}".format(electric_demand_curve.points))

            self.vip.pubsub.publish(peer='pubsub',
                                    topic='mixmarket/reserve_demand',
                                    message={
                                        "reserve_power": list(tess_power_reserve),
                                        "sender": self.agent_name
                                    })
            success = True
        return success

    def _calculate_demand(self, peer, sender, bus, topic, headers, message):
        prices = message['prices']
        reserve_prices = message['reserve_prices']
        tess_power_inject, tess_power_reserve = self.model.run_tess_optimization(prices,
                                                                                reserve_prices,
                                                                                self.oat_predictions,
                                                                                self.cooling_load_copy)
        tess_power_inject = [i * -1 for i in tess_power_inject]
        self.vip.pubsub.publish(peer='pubsub',
                                topic='mixmarket/tess_bess_demand',
                                message={
                                    "power": tess_power_inject,
                                    "reserve_power": tess_power_reserve,
                                    "sender": self.agent_name
                                })

    def determine_control(self, sets, prices, price):
        return self.model.calculate_control(self.current_datetime, self.cooling_load_copy)

    def determine_price_min_max(self):
        """
        Determine minimum and maximum price from 24-hour look ahead prices.  If the TNS
        market architecture is not utilized, this function must be overwritten in the child class.
        :return:
        """
        prices = self.determine_prices()
        price_min = prices[0]
        price_max = prices[len(prices)-1]
        return price_min, price_max

def main():
    """Main method called to start the agent."""
    utils.vip_main(TESSAgent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
