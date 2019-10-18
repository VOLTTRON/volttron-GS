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
from volttron.platform.vip.agent import Agent, Core
from volttron.pnnl.models import Model

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
        self.init_markets()
    #
    # @Core.receiver('onstart')
    # def setup(self, sender, **kwargs):
    #     """
    #     On start.
    #     :param sender:
    #     :param kwargs:
    #     :return:
    #     """
    #     self.vip.pubsub.subscribe(peer='pubsub',
    #                               prefix='mixmarket/start_new_cycle',
    #                               callback=self.update_prices)
    #
    # def update_prices(self, peer, sender, bus, topic, headers, message):
    #     _log.debug("Get prices prior to market start.")
    #     self.energy_prices = message['prices']  # Array of prices
    #     self.reserve_prices = message.get('reserve_prices', None)


    def translate_aggregate_demand(self, chilled_water_demand, index):
        electric_demand_curve = PolyLine()
        reserve_demand_curve = PolyLine()
        oat = self.oat_predictions[index] if self.oat_predictions else None
        cooling_load = []

        if len(chilled_water_demand) == self.numHours:
            #point.x = quantity, point.y = price
            # Assuming points.x is cooling load, points.y is price (what about reserve price???)
            for point in chilled_water_demand:
                cooling_load.append(point.x)

            tess_power_inject, tess_power_reserve, tess_soc = self.model.run_optimization(self.market_prices,
                                                                                        self.reserve_market_prices,
                                                                                        self.oat_predictions,
                                                                                        cooling_load)
            for i in range(0, len(self.market_prices)):
                electric_demand_curve.add(Point(self.energy_prices[i], tess_power_inject[i]))

            for i in range(0, len(self.reserve_market_prices)):
                reserve_demand_curve.add(Point(self.reserve_prices[i], tess_power_reserve[i]))

            self.consumer_demand_curve['electric'][index] = electric_demand_curve
            self.consumer_reserve_demand_curve['electric'][index] = reserve_demand_curve

        _log.debug("{}: electric demand : {}".format(self.agent_name, electric_demand_curve.points))
        _log.debug("{}: reserve demand : {}".format(self.agent_name, reserve_demand_curve.points))


def main():
    """Main method called to start the agent."""
    utils.vip_main(TESSAgent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
