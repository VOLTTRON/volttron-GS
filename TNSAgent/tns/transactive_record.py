from datetime import datetime

from time_interval import TimeInterval
from helpers import format_ts
from measurement_type import MeasurementType


class TransactiveRecord:
    # TransactiveRecord - transactive signal record format
    # This is primarily a struct, although is might include a constructor method.

    def __init__(self, ti, rn, mp, p, pu=0.0, cost=0.0, rp=0.0, rpu=0.0, v=0.0, vu=0.0, e_type=MeasurementType.PowerReal):
        # NOTE: As of Feb 2018, ti is forced to be text, the time interval name,
        # not a TimeInterval object.
        # ti - TimeInterval object (that must be converted to its name)
        # rn - record number, a nonzero integer
        # mp - marginal price [$/kWh]
        # p  - power [avg.kW]
        # e_type - intiger indicating energy type
        # varagin - Matlab variable allowing additional input arguments.

        # These are the four normal arguments of the constructor.
        # NOTE: Use the time interval ti text name, not a TimeInterval object itself.
        if isinstance(ti, TimeInterval):  # if isa(ti, 'TimeInterval')
            # A TimeInterval object argument must be represented by its text name.
            self.timeInterval = ti.name
        else:
            # Argument ti is most likely received as a text string name. Further
            # validation might be used to make sure that ti is a valid name of an
            # active time interval.
            self.timeInterval = ti

        self.record = rn  # a record number (0 refers to the balance point)
        self.marginalPrice = mp  # marginal price [$/kWh]
        self.power = p  # power [avg.kW]

        # Source and target are obvious from Neighbor and filenames. Omit
        self.powerUncertainty = pu  # relative [dimensionless]
        self.cost = cost  # ?
        self.reactivePower = rp  # [avg.kVAR]
        self.reactivePowerUncertainty = rpu  # relative [dimensionless]
        self.voltage = v  # [p.u.]
        self.voltageUncertainty = vu  # relative [dimensionless]


        # Finally, create the timestamp that captures when the record is created.
        # Format example: "180101:000001" is one second after the new year 2018
        #self.timeStamp = string(datetime('now', 'Format', 'yyMMdd:HHmmss'))
        #self.timeStamp = format_ts(datetime.now())
        self.timeStamp = datetime.utcnow()
        
        # record the type of energy this applies to
        self.e_type = e_type
