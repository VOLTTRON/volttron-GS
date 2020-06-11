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
import json
import datetime
from .tcc_models import Model
from volttron.platform.agent import utils
import numpy as np
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.poly_line_factory import PolyLineFactory
from volttron.platform.agent.base_market_agent.point import Point


class MarketContainer(object):
    def __init__(self):
        self.container = {}

    def add_member(self, tag, config_path):
        config = utils.load_config(config_path)
        self.container[tag] = Model(config, self)


class PredictionManager(object):
    def __init__(self, config):
        self.price_multiplier = config.get("price_multiplier", 1.0)
        self.calculating_predictions = False
        self.prices = None
        self.previous_days_prices = None
        self.hourly_electric_demand = []
        self.hourly_chilled_water_demand = []

        self.electric_demand = {}
        self.chilled_water_demand = {}
        self.market_container = MarketContainer()
        config_directory = config.pop("config_directory")
        self.ahus = config.get("AHU", {})
        self.lights = config.get("LIGHT", {})

        for ahu, vav_list in self.ahus.items():
            for vav in vav_list:
                print("VAV: {}".format(vav))
                config_path = "/".join([config_directory, vav + ".config"])
                self.market_container.add_member(vav, config_path)
            config_path = "/".join([config_directory, ahu + ".config"])
            self.market_container.add_member(ahu, config_path)
        for light in self.lights:
            config_path = "/".join([config_directory, light + ".config"])
            self.market_container.add_member(light, config_path)

    def do_predictions(self, prices, oat_predictions, _date, new_cycle=False, first_day=False):
        """
        Do 24 hour predictions for all devices.
        :param prices:
        :param oat_predictions:
        :param new_cycle:
        :param first_day:
        :return:
        """

        # Needs to know first days iterations.  Will use
        # projected prices on first day.  After first day will
        # use previous 24-hours prices
        self.calculating_predictions = True
        if first_day:
            self.prices = self.determine_prices(prices)
        if self.prices.size and not first_day and new_cycle:
            self.previous_days_prices = self.prices
        price_range = self.previous_days_prices if self.previous_days_prices is not None else self.prices
        self.electric_demand = {}
        self.chilled_water_demand = {}
        for _hour in range(24):
            price = prices[_hour]
            oat = oat_predictions[_hour]
            self.hourly_electric_demand = []
            self.hourly_chilled_water_demand = []
            for ahu, vav_list in self.ahus.items():
                self.market_container.container[ahu].model.air_demand = []
                for vav in vav_list:
                    occupied = self.market_container.container[vav].check_schedule(_date, _hour)
                    air_demand = self.market_container.container[vav].model.create_demand_curve(price_range, price, oat, _hour, occupied, new_cycle)
                    self.market_container.container[ahu].model.air_demand.append(air_demand)

                self.market_container.container[ahu].model.aggregate_load()
                self.hourly_electric_demand.append(self.market_container.container[ahu].model.create_electric_demand())
                self.hourly_chilled_water_demand.append(self.market_container.container[ahu].model.create_chilled_water_demand(oat))

            for light in self.lights:
                occupied = self.market_container.container[light].check_schedule(_date, _hour)
                electric_demand = self.market_container.container[light].model.create_demand_curve(price_range, price, occupied)
                self.hourly_electric_demand.append(electric_demand)

            self.electric_demand[_hour] = self.aggregate_load(self.hourly_electric_demand)
            self.chilled_water_demand[_hour] = self.aggregate_load(self.hourly_chilled_water_demand)
            print("hour {} - electric_demand: {}".format(_hour, self.electric_demand[_hour].points))
            print("hour {} - chilled_water: {}".format(_hour, self.chilled_water_demand[_hour].points))
        self.prices = self.determine_prices(prices)
        self.calculating_predictions = False

    def determine_prices(self, _prices):
        """
        Uses 24 hour prices to determine minimum and maximum price
        for construction of demand curve.
        :param _prices:
        :return:
        """
        avg_price = np.mean(_prices)
        std_price = np.std(_prices)
        price_min = avg_price - self.price_multiplier * std_price
        price_max = avg_price + self.price_multiplier * std_price
        price_array = np.linspace(price_min, price_max, 11)
        return price_array

    @staticmethod
    def aggregate_load(curves):
        aggregate_curve = PolyLineFactory.combine(curves, 11)
        return aggregate_curve


# x = PredictionManager()
# message = [{"MixedAirTemperature": 23, "ReturnAirTemperature": 25, "DischargeAirTemperature": 13}, {}]
# x.market_container.container["AHU1"].update_data(None, None, None, None, None, message)
# _prices = np.linspace(0.035, 0.06, 24)
# oat_predictions = [25]*24
# new_cycle=True
# first_day=True
# x.do_predictions(_prices, oat_predictions, datetime.datetime.now(), new_cycle=new_cycle, first_day=first_day)
