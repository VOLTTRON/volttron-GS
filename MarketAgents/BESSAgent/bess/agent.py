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
from volttron.pnnl.transactive_base.transactive.transactive import TransactiveBase
from volttron.pnnl.transactive_base.transactive.aggregator_base import Aggregator
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.pnnl.models import Model
from volttron.platform.vip.agent import Agent, Core

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


class BESSAgent(TransactiveBase, Model):
    """
    The BESS Agent participates in Electricity Market as supplier of electricity.
    """

    def __init__(self, config_path, **kwargs):
        try:
            config = utils.load_config(config_path)
        except Exception.StandardError:
            config = {}
        self.agent_name = config.get("agent_name", "bess_agent")
        model_config = config.get("model_parameters", {})
        TransactiveBase.__init__(self, config, **kwargs)
        Model.__init__(self, model_config, **kwargs)
        self.init_markets()
        self.numHours = 24
        self.indices = [None]*self.numHours

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.debug("BESS onstart")
        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/calculate_demand',
                                  callback=self._calculate_demand)

    def offer_callback(self, timestamp, market_name, buyer_seller):
        market_index = self.market_name.index(market_name)

        self.indices[market_index] = market_name
        optimization_ready = all([False if i is None else True for i in self.indices])
        if optimization_ready:
            _log.debug("BESS: market_prices = {}".format(self.market_prices))
            _log.debug("BESS: reserve_market_prices = {}".format(self.reserve_market_prices))
            bess_power_inject, bess_power_reserve, bess_soc = self.model.run_bess_optimization(self.market_prices,
                                                                                               self.reserve_market_prices)
            bess_power_inject = [-i for i in bess_power_inject]
            _log.debug("BESS: translate_aggregate_demand bess_power_inject: {}, bess_power_reserve: {}".format(
                bess_power_inject,
                bess_power_reserve))
            self.indices = [None] * self.numHours
            price_min, price_max = self.determine_price_min_max()
            _log.debug("BESS: price_min: {}, price_max: {}".format(price_min, price_max))
            for name in self.market_name:
                index = self.market_name.index(name)
                electric_demand_curve = PolyLine()
                electric_demand_curve.add(Point(bess_power_inject[index], price_min))
                electric_demand_curve.add(Point(bess_power_inject[index], price_max))
                self.demand_curve[market_index] = electric_demand_curve
                self.make_offer(name, buyer_seller, electric_demand_curve)
                _log.debug("BESS: make_offer: market name: {}, electric demand : Pt: {}, index: {}".format(name,
                                                                                                           electric_demand_curve.points,
                                                                                                           index))
                self.update_flag[market_index] = True

            self.vip.pubsub.publish(peer='pubsub',
                                    topic='mixmarket/reserve_demand',
                                    message={
                                        "reserve_power": list(bess_power_reserve),
                                        "sender": self.agent_name
                                    })

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

    def determine_control(self, sets, prices, price):
        return self.model.calculate_control(self.current_datetime)

    def _calculate_demand(self, peer, sender, bus, topic, headers, message):
        prices = message['prices']
        reserve_prices = message['reserve_prices']
        bess_power_inject, bess_power_reserve, bess_soc = self.model.run_bess_optimization(prices,
                                                                                           reserve_prices)
        bess_power_inject = [-i for i in bess_power_inject]
        self.vip.pubsub.publish(peer='pubsub',
                                topic='mixmarket/tess_bess_demand',
                                message={
                                    "power": bess_power_inject,
                                    "reserve_power": bess_power_reserve,
                                    "sender": self.agent_name
                                })

def main():
    """Main method called to start the agent."""
    utils.vip_main(BESSAgent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass