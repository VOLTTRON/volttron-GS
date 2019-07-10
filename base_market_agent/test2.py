from poly_line import PolyLine
from poly_line_factory import PolyLineFactory
from point import Point

Curve1=PolyLine()
Curve1.add(Point(price=0.01,quantity=10.))
Curve1.add(Point(price=0,quantity=10.))
Curve1.add(Point(price=0.5,quantity=5.))
Curve1.add(Point(price=0.03,quantity=5.))

	
Curve2=PolyLine()
Curve2.add(Point(price=0,quantity=12.))
Curve2.add(Point(price=0.02,quantity=12.))
Curve2.add(Point(price=0.04,quantity=3.))
Curve2.add(Point(price=0.5,quantity=3.))

aggregated_curve=PolyLineFactory.combine_withoutincrement([Curve1,Curve2])

print Curve1.points
print aggregated_curve.points
Curve3=PolyLine()
Curve3.add(Point(price=0.02,quantity=60))
Curve3.add(Point(price=0.02,quantity=60))
print Curve3.points
print PolyLine.intersection(aggregated_curve,Curve3)


#supply=PolyLine()
#supply.add(Point(price=0.02,quantity=40))
#supply.add(Point(price=0.02,quantity=0))


#print PolyLine.poly_intersection(aggregated_curve,supply)