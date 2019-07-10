from poly_line import PolyLine
from point import Point
from poly_line_factory import PolyLineFactory


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
print intersection
#for point in combined_curves.points:
 #    print point


