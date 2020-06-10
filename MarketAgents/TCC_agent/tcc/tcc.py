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
from .tcc_market import PredictionManager
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


class TCCAgent(TransactiveBase):
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
        self.numHours = 24
        self.cooling_load = [None] * self.numHours
        self.init_markets()
        self.indices = [None] * self.numHours
        self.cooling_load_copy = self.cooling_load[:]

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.debug("TCC onstart")
        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/make_tcc_predictions',
                                  callback=self.make_tcc_predictions)
        self.tcc = PredictionManager(self.tcc_config)

    def offer_callback(self, timestamp, market_name, buyer_seller):
        # Verify that all tcc predictions for day have finished
        while self.tcc.calculating_predictions:
            _log.debug("SLEEP")
            gevent.sleep(0.1)

        _log.debug("PRICES: {}".format(self.market_prices))
        for idx in range(24):
            price = self.market_prices[idx]
            self.cooling_load[idx] = self.tcc.chilled_water_demand[idx].x(price)

        self.vip.pubsub.publish(peer='pubsub',
                                topic='tcc/cooling_demand',
                                message=self.cooling_load,
                                headers={})
        # Only need to do this once so return on all
        # other call backs
        if market_name != self.market_name[0]:
            return
        # Check just for good measure
        _log.debug("market_prices = {}".format(self.market_prices))
        _log.debug("oat_predictions = {}".format(self.oat_predictions))
        _log.debug("TESS: cooling_load = {}".format(self.cooling_load))
        T_out = [-0.05 * (t - 14.0) ** 2 + 30.0 for t in range(1, 25)]
        # do optimization to obtain power and reserve power
        tess_power_inject, tess_power_reserve = self.model.run_tess_optimization(self.market_prices,
                                                                                 self.reserve_market_prices,
                                                                                 self.oat_predictions,
                                                                                 # T_out,
                                                                                 self.cooling_load)
        tess_power_inject = [i * -1 for i in tess_power_inject]
        self.cooling_load = [None] * self.numHours
        _log.debug("TESS: offer_callback tess_power_inject: {}, tess_power_reserve: {}".format(tess_power_inject,
                                                                                               tess_power_reserve))
        for i in range(0, len(self.market_prices)):
            self.make_offer(self.market_name[i], buyer_seller, self.tcc.electric_demand[i])
            _log.debug("TCC hour {}-- electric demand  {}".format(i, self.tcc.electric_demand[i].points))

    def make_tcc_predictions(self, peer, sender, bus, topic, headers, message):
        """
        Run tcc predictions for building electric and chilled water market.
        Message sent by campus agent on topic 'mixmarket/make_tcc_predictions'.

        message = dict; {
            "converged": bool - market converged
            "prices": array - next days 24 hour hourly demand prices,
            "reserved_prices": array - next days 24 hour hourly reserve prices
            "start_of_cycle": bool - start of cycle
            "hour": int for current hour,
            "prediction_date": string - prediction date,
            "temp": array - next days 24 hour hourly outdoor temperature predictions
        }
        """
        self.tcc.calculating_predictions = True
        new_cycle = message["start_of_cycle"]
        if new_cycle and self.first_day and self.iteration_count > 0:
            self.first_day = False
            self.iteration_count = 1
        elif new_cycle:
            self.iteration_count = 1
        else:
            self.iteration_count += 1
        _log.debug("new_cycle %s - first_day %s - iteration_count %s",
                   new_cycle, self.first_day, self.iteration_count)
        oat_predictions = message["temp"]
        prices = message["prices"]
        _date = parse(message["prediction_date"])
        self.tcc.do_predictions(prices, oat_predictions, _date, new_cycle=new_cycle, first_day=self.first_day)

    def determine_control(self, sets, prices, price):
        for ahu, vav_list in self.tcc.ahus.items():
            # Assumes all devices are on same occupancy schedule.  Potential problem
            occupied = self.tcc.check_current_schedule(self.current_time)
            for vav in vav_list:
                actuator = self.market_container.container[vav].actuator
                point_topic = self.market_container.container[vav].ct_topic
                value = self.market_container.container[vav].determine_set(prices, price)
                if occupied:
                    self.vip.rpc.call(actuator,
                                      'set_point',
                                      self.core.identity,
                                      point_topic,
                                      value).get(timeout=15)
            for light in self.tcc.lights:
                actuator = self.market_container.container[light].actuator
                point_topic = self.market_container.container[light].ct_topic
                value = self.market_container.container[light].determine_set(prices, price)
                if occupied:
                    self.vip.rpc.call(actuator,
                                      'set_point',
                                      self.core.identity,
                                      point_topic,
                                      value).get(timeout=15)

    def update_state(self, market_index, sched_index, price):
        pass


def main():
    """Main method called to start the agent."""
    utils.vip_main(TCCAgent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
