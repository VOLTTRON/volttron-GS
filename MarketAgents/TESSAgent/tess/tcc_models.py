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
from dateutil.parser import parse
from volttron.pnnl.models import input_names as data_names
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.poly_line_factory import PolyLineFactory
from volttron.platform.agent.base_market_agent.point import Point
import sys
import numpy as np


def clamp(value, x1, x2):
    min_value = min(x1, x2)
    max_value = max(x1, x2)
    return min(max(value, min_value), max_value)


class Model(object):
    def __init__(self, config, parent):

        outputs = config.get("outputs")
        schedule = config.get("schedule", {})
        model_parms = config.get("model_parameters")
        self.input_topics = set()
        self.inputs = {}
        self.parent = parent

        if model_parms is None:
            print("No model parms")
            return
        model_type = model_parms.get("model_type")
        self.schedule = {}
        self.init_schedule(schedule)
        # Parse inputs from config
        # these could be used to extend this standalone code
        # for single timestep
        inputs = config.get("inputs")
        for input_info in inputs:
            try:
                point = input_info["point"]
                mapped = input_info["mapped"]
                topic = input_info["topic"]
            except KeyError as ex:
                print("Exception on init_inputs %s", ex)
                sys.exit()
            value = input_info.get("initial_value")
            self.inputs[mapped] = {point: value}
            self.input_topics.add(topic)
        if model_type == "vav.firstorderzone":
            flexibility = outputs[0].get("flexibility_range")
            control_flexibility = outputs[0].get("control_flexibility")
            off_setpoint = outputs[0].get("off_setpoint")
            ct_topic = outputs[0].get("topic")
            actuator = outputs[0].get("actuator")

            min_flow = float(flexibility[1])
            max_flow = float(flexibility[0])
            tmin = float(control_flexibility[0])
            tmax = float(control_flexibility[1])

            model_parms.update({"min_flow": min_flow})
            model_parms.update({"max_flow": max_flow})
            model_parms.update({"actuator": actuator})

            model_parms.update({"tmin": tmin})
            model_parms.update({"tmax": tmax})
            model_parms.update({"ct_topic": ct_topic})

            model_parms.update({"off_setpoint": off_setpoint})
            self.model = FirstOrderZone(model_parms)
        if model_type == "ahuchiller.ahuchiller":
            self.model = Ahu(model_parms)
        if model_type == "light.simple":
            ct_topic = outputs[0].get("topic")
            model_parms.update({"ct_topic": ct_topic})
            flexibility = outputs[0].get("flexibility_range")
            min_lighting = float(flexibility[1])
            max_lighting = float(flexibility[0])
            off_setpoint = outputs[0].get("off_setpoint")
            model_parms.update({"dol_min": min_lighting})
            model_parms.update({"dol_max": max_lighting})
            model_parms.update({"off_setpoint": off_setpoint})
            actuator = outputs[0].get("actuator")
            model_parms.update({"actuator": actuator})
            self.model = LightSimple(model_parms)

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

    def init_subscriptions(self):
        """
        Create topic subscriptions for devices.
        :return:
        """
        for topic in self.input_topics:
            print('Subscribing to: ' + topic)
            self.parent.vip.pubsub.subscribe(peer='pubsub',
                                             prefix=topic,
                                             callback=self.update_data)

    def update_data(self, peer, sender, bus, topic, headers, message):
        """
        Each time data comes in on message bus from MasterDriverAgent
        update the data for access by model.
        :param data: dict; key value pairs from master driver.
        :return:
        """
        data = message[0]
        print("inputs: {}".format(self.inputs))
        for name, input_data in self.inputs.items():
            print(name, input_data)
            for point, value in input_data.items():
                if point in data:
                    self.inputs[name][point] = data[point]
        self.model.update_inputs(self.inputs)

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

    def check_schedule(self, dt, _hour):
        """
        Check if the hour/day for current prediction is scheduled
        as occupied.  If no schedule is provided all times are
        considered as occupied.
        :param dt:
        :param _hour:
        :return:
        """
        if not self.schedule:
            occupied = True
            return occupied
        current_schedule = self.schedule[dt.weekday()]
        if "always_on" in current_schedule:
            occupied = True
            return occupied
        if "always_off" in current_schedule:
            occupied = False
            return occupied
        _start = current_schedule["start"]
        _end = current_schedule["end"]
        prediction_time = dt.replace(hour=_hour, minute=0, second=0).time()
        if _start <= prediction_time < _end:
            occupied = True
        else:
            occupied = False
        return occupied

    def check_current_schedule(self, _dt):
        """
        Check if the hour/day for current prediction is scheduled
        as occupied.  If no schedule is provided all times are
        considered as occupied.
        :param dt:
        :param _hour:
        :return:
        """
        if not self.schedule:
            occupied = True
            return occupied
        current_schedule = self.schedule[_dt.weekday()]
        if "always_on" in current_schedule:
            occupied = True
            return occupied
        if "always_off" in current_schedule:
            occupied = False
            return occupied
        _start = current_schedule["start"]
        _end = current_schedule["end"]
        if _start <= _dt < _end:
            occupied = True
        else:
            occupied = False
        return occupied

class FirstOrderZone(object):
    """VAV firstorder zone tcc model."""
    def __init__(self, model_parms):
        self.mDotMin = model_parms['min_flow']
        self.mDotMax = model_parms['max_flow']
        self.tMinAdj = model_parms['tmin']
        self.tMaxAdj = model_parms['tmax']
        try:
            self.a1 = model_parms['a1']
            self.a2 = model_parms['a2']
            self.a3 = model_parms['a3']
            self.a4 = model_parms['a4']
        except KeyError:
            print("Missing FirstOrderZone model parameter!")
            sys.exit()

        self.oat_name = data_names.OAT
        self.sfs_name = data_names.SFS
        self.zt_name = data_names.ZT
        self.zdat_name = data_names.ZDAT
        self.zaf_name = data_names.ZAF
        self.ct_topic = model_parms['ct_topic']
        self.actuator = model_parms.get("actuator", "platform.actuator")
        self.vav_flag = model_parms.get("vav_flag", True)
        if self.vav_flag:
            self.get_q = self.getM
        else:
            self.get_q = self.getdT

        self.sets = np.linspace(self.tMinAdj, self.tMaxAdj, 11)
        self.tNomAdj = np.mean(self.sets)
        self.tIn = [self.tNomAdj] * 24
        self.tpre = self.tNomAdj
        self.name = "FirstOrderZone"

    def getM(self, oat, temp, temp_stpt, index):
        M = temp_stpt*self.a1[index]+temp*self.a2[index]+oat*self.a3[index]+self.a4[index]
        M = clamp(M, self.mDotMin, self.mDotMax)
        return M

    def getdT(self, oat, temp, temp_stpt, index):
        dT = temp_stpt * self.a1[index] + temp * self.a2[index] + oat * self.a3[index] + self.a4[index]
        return dT

    def create_demand_curve(self, prices, price, oat, _hour, occupied, new_cycle):
        curve = PolyLine()
        tset = self.determine_set(prices, price)
        if new_cycle:
            self.tpre = self.tIn[-1]
        if _hour == 0:
            temp = self.tpre
        else:
            temp = self.tIn[_hour-1]
        for _price in prices:
            if occupied:
                q = self.get_q(oat, temp, tset, _hour)
            else:
                q = 0
            curve.add(Point(q, _price))
        self.tIn[_hour] = tset
        return curve

    def determine_set(self, prices, price):
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
        tset = np.interp(price, prices, self.sets)
        return tset

    def update_inputs(self, inputs):
        """
        For injection of realtime data from building.  Not needed for
        day ahead demand predictions.
        :param inputs:
        :return:
        """
        pass


class Ahu(object):
    """AHU tcc model."""
    def __init__(self, model_parms):
        self.air_demand = []
        self.aggregate_air_demand = []
        self.aggregate_chilled_water_demand = []
        equipment_conf = model_parms.get("equipment_configuration")
        model_conf = model_parms.get("model_configuration")
        self.cpAir = model_conf["cpAir"]
        self.c0 = model_conf['c0']
        self.c1 = model_conf['c1']
        self.c2 = model_conf['c2']
        self.c3 = model_conf['c3']
        self.cop = model_conf['COP']
        self.mDotAir = model_conf['mDotAir']
        self.vav_flag = model_conf.get("vav_flag", True)

        self.has_economizer = equipment_conf["has_economizer"]
        self.economizer_limit = equipment_conf["economizer_limit"]
        self.min_oaf = equipment_conf.get("minimum_oaf", 0.15)
        self.vav_flag = equipment_conf.get("variable-volume", True)
        self.sat_setpoint = equipment_conf["supply-air sepoint"]
        self.tDis = self.sat_setpoint
        self.building_chiller = equipment_conf["building chiller"]
        self.tset_avg = equipment_conf["nominal zone-setpoint"]
        self.power_unit = model_conf.get("unit_power", "kw")
        self.mDotAir = model_conf["mDotAir"]

        self.fan_power = 0.
        self.coil_load = 0.
        self.name = 'AhuChiller'

        self.sfs_name = data_names.SFS
        self.mat_name = data_names.MAT
        self.dat_name = data_names.DAT
        self.saf_name = data_names.SAF
        self.oat_name = data_names.OAT
        self.rat_name = data_names.RAT

    def update_inputs(self, inputs):
        pass

    def input_zone_load(self, q_load):
        if self.vav_flag:
            self.mDotAir = q_load
        else:
            self.tDis = q_load

    def calculate_electric_load(self):
        return self.calculate_fan_power()

    def calculate_fan_power(self):
        if self.power_unit == 'W':
            fan_power = (self.c0 + self.c1 * self.mDotAir + self.c2 * pow(self.mDotAir, 2) + self.c3 * pow(self.mDotAir, 3))
        else:
            fan_power = self.c0 + self.c1 * self.mDotAir + self.c2 * pow(self.mDotAir, 2) + self.c3 * pow(self.mDotAir, 3)
        return fan_power

    def calculate_coil_load(self, oat):
        if self.has_economizer:
            if oat < self.tDis:
                coil_load = 0.0
            elif oat < self.economizer_limit:
                coil_load = self.mDotAir * self.cpAir * (self.tDis - oat)
            else:
                mat = self.tset_avg * (1.0 - self.min_oaf) + self.min_oaf * oat
                coil_load = self.mDotAir * self.cpAir * (self.tDis - mat)
        else:
            mat = self.tset_avg * (1.0 - self.min_oaf) + self.min_oaf * oat
            coil_load = self.mDotAir * self.cpAir * (self.tDis - mat)

        if coil_load > 0:  # heating mode is not yet supported!
            coil_load = 0.0
        return coil_load

    def aggregate_load(self):
        aggregate_curve = PolyLineFactory.combine(self.air_demand, 11)
        self.aggregate_air_demand = aggregate_curve

    def create_electric_demand(self):
        electric_demand_curve = PolyLine()
        for point in self.aggregate_air_demand.points:
            self.input_zone_load(point.x)
            electric_demand_curve.add(Point(price=point.y, quantity=self.calculate_electric_load()))
        return electric_demand_curve

    def create_chilled_water_demand(self, oat):
        electric_demand_curve = PolyLine()
        for point in self.aggregate_air_demand.points:
            self.input_zone_load(point.x)
            electric_demand_curve.add(Point(price=point.y, quantity=self.calculate_coil_load(oat)))
        return electric_demand_curve


class LightSimple(object):
    """
    Lighting model for tcc standalone.
    """
    def __init__(self, model_parms, **kwargs):
        self.rated_power = model_parms["rated_power"]
        min_lighting = model_parms.get("dol_min", 0.7)
        max_lighting = model_parms.get("dol_min", 0.9)
        self.off_setpoint = model_parms.get("off_setpoint")
        self.sets = np.linspace(max_lighting, min_lighting, 11)
        self.get_q = self.predict
        self.ct_topic = model_parms['ct_topic']
        self.actuator = model_parms.get("actuator", "platform.actuator")

    def update_inputs(self, inputs):
        pass

    def create_demand_curve(self, prices, _price, occupied):
        if occupied:
            _set = self.determine_set(prices, _price)
        else:
            _set = self.off_setpoint
        curve = PolyLine()
        for _price in prices:
            curve.add(Point(self.get_q(_set), _price))
        return curve

    def predict(self, _set):
        return _set*self.rated_power

    def determine_set(self, prices, price):
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
        tset = np.interp(price, prices, self.sets)
        return tset

