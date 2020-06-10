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
import gevent
from dateutil.parser import parse
import logging
from volttron.platform.agent import utils
from volttron.pnnl.transactive_base.transactive.aggregator_base import Aggregator
from volttron.pnnl.transactive_base.transactive.transactive import TransactiveBase
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.poly_line_factory import PolyLineFactory
from volttron.pnnl.models import Model
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


class TESSAgent(TransactiveBase, Model):
    """
    The TESS Agent participates in Electricity Market as consumer of electricity at fixed price.
    It participates in internal Chilled Water market as supplier of chilled water at fixed price.
    """

    def __init__(self, config_path, **kwargs):
        try:
            config = utils.load_config(config_path)
        except Exception.StandardError:
            config = {}
        tcc_config_directory = config.get("tcc_config_directory", "tcc_config.json")
        try:
            self.tcc_config = utils.load_config(tcc_config_directory)
        except:
            _log.error("Could not locate tcc_config_directory in tess config file!")
            self.core.stop()
        self.first_day = True
        self.iteration_count = 0
        self.tcc = None
        self.agent_name = config.get("agent_name", "tess_agent")
        model_config = config.get("model_parameters", {})
        TransactiveBase.__init__(self, config, **kwargs)
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
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='tcc/cooling_demand',
                                  callback=self.calculate_load)

    def offer_callback(self, timestamp, market_name, buyer_seller):
        if market_name != self.market_name[-1]:
            return
        while None in self.cooling_load:
            gevent.sleep(0.1)
        _log.debug("TESS: market_prices = {}".format(self.market_prices))
        _log.debug("TESS: reserve_market_prices = {}".format(self.reserve_market_prices))
        _log.debug("TESS: oat_predictions = {}".format(self.oat_predictions))
        _log.debug("TESS: cooling_load = {}".format(self.cooling_load))
        T_out = [-0.05 * (t - 14.0) ** 2 + 30.0 for t in range(1, 25)]
        # do optimization to obtain power and reserve power
        tess_power_inject, tess_power_reserve = self.model.run_tess_optimization(self.market_prices,
                                                                                 self.reserve_market_prices,
                                                                                 self.oat_predictions,
                                                                                 # T_out,
                                                                                 self.cooling_load)
        tess_power_inject = [i * -1 for i in tess_power_inject]
        _log.debug("TESS: offer_callback tess_power_inject: {}, tess_power_reserve: {}".format(tess_power_inject,
                                                                                               tess_power_reserve))
        price_min, price_max = self.determine_price_min_max()
        _log.debug("TESS: price_min: {}, price_max: {}".format(price_min, price_max))
        for i in range(0, len(self.market_prices)):
            electric_demand_curve = PolyLine()
            electric_demand_curve.add(Point(tess_power_inject[i], price_min))
            electric_demand_curve.add(Point(tess_power_inject[i], price_max))
            self.make_offer(self.market_name[i], BUYER, electric_demand_curve)
        self.vip.pubsub.publish(peer='pubsub',
                                topic='mixmarket/reserve_demand',
                                message={
                                    "reserve_power": list(tess_power_reserve),
                                    "sender": self.agent_name
                                })
        self.cooling_load = [None] * self.numHours


    def calculate_load(self, peer, sender, bus, topic, headers, message):
        # Verify that all tcc predictions for day have finished
        _log.debug("PRICES: {}".format(self.market_prices))
        for idx in range(24):
            price = self.market_prices[idx]
            self.cooling_load[idx] = message[idx]

    def _calculate_demand(self, peer, sender, bus, topic, headers, message):
        """

        """
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
        # I cannot find this method anywhere
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

    def update_state(self, market_index, sched_index, price):
        pass


def main():
    """Main method called to start the agent."""
    utils.vip_main(TESSAgent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
