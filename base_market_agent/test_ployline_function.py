# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2020, Battelle Memorial Institute
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

import logging

import gevent

from volttron.platform.agent import utils
from volttron.platform.agent.base_market_agent.error_codes import NOT_FORMED
from volttron.platform.agent.base_market_agent.market_registration import MarketRegistration
from .poly_line import PolyLine
from .point import Point
from .poly_line_factory import PolyLineFactory


# demand_curve1 = PolyLine()
#
# demand_curve2 = PolyLine()
#
# demand_curve3 = PolyLine()
#
# demand_curve1.add(Point(price=0.1, quantity=0))
#
# demand_curve1.add(Point(price=1, quantity=0))
#
#
# demand_curve2.add(Point(price=0.2, quantity=0))
#
# demand_curve2.add(Point(price=0.8, quantity=0))
#
#
# demand_curve3.add(Point(price=-0.0, quantity=0))
#
# demand_curve3.add(Point(price=0.8, quantity=0))
#
# curves = [demand_curve1, demand_curve2, demand_curve3]
# combined_curves = PolyLineFactory.combine(curves, 6)
#
# Curve4=PolyLine()
# Curve4.add(Point(price=0.02,quantity=0.5))
# Curve4.add(Point(price=0.02,quantity=0.7))

x = [[19.0666, 0.04581211179062671], [19.0666, 0.045195549240425105], [64.4874, 0.039687502953079455], [67.2112, 0.034179456665733805], [67.2112, 0.03226979900210781]]
demand = PolyLine()
for point in x:
    demand.add(Point(price=point[1], quantity=point[0]))
y = [[0.0, 0.04159599291498382], [10000.0, 0.04159599291498382]]
supply = PolyLine()
for point in y:
    supply.add(Point(price=point[1], quantity=point[0]))

intersection = PolyLine.intersection(supply,demand)
print("intersection: %s", intersection)
#for point in combined_curves.points:
 #    print point


