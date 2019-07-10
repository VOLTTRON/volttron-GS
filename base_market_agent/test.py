from poly_line import PolyLine
from point import Point

def Remove(duplicate): 
    final_list = [] 
    for num in duplicate: 
        if num not in final_list: 
            final_list.append(num) 
    return final_list

line1=PolyLine()
line1.add(Point(price=0.01,quantity=10))
line1.add(Point(price=0.1,quantity=10))
line1.add(Point(price=0.3,quantity=5))
line1.add(Point(price=0.5,quantity=5))

line2=PolyLine()
line1.add(Point(price=0.01,quantity=10))
line2.add(Point(price=0.05,quantity=10))
line2.add(Point(price=0.05,quantity=0))
line1.add(Point(price=0.5,quantity=5))

line3=PolyLine()
line3.add(Point(price=0.35,quantity=10))
line3.add(Point(price=0.35,quantity=0))


a=line1.vectorize()[1]+line2.vectorize()[1]

print(Remove(a)) 

#print PolyLine.intersection(line1,line2)

#print PolyLine.poly_intersection(line1,line2)

#print PolyLine.intersection(line1,line3)

#print PolyLine.poly_intersection(line1,line3)