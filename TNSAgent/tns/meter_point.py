# MeterPoint Base Class
#
# A MeterPoint may correlate directly with a meter. It necessarily
# corresponds to one measurement type (see MeasurementType enumeration) and
# measurement location within the circuit. Therefore, a single physical
# meter might be the source of more than one MeterPoint.
#
#   VERSIONING
#   0.2 2017-11 Hammerstrom
#       - Added properties for measurement units and last reading and
#         meter-reading time interval.
#   0.1 2017-11 Hammerstrom
#       - Original draft

from datetime import datetime, date, timedelta

from measurement_type import MeasurementType
from measurement_unit import MeasurementUnit
from helpers import format_ts, format_date


class MeterPoint:
    # DATAFILE
    # Text name that identifies a data file, database, or historian
    # where meter data points are to be stored. A default is provided,
    # but a meaningful filename should be used.
    today = date.today()
    dateFile = 'MP' + format_date(today)

    # DESCRIPTION
    description = ''

    # LAST MEASUREMENT
    # The measurement point datum that was collected during the last
    # reading update. This measurement must be of the measurement type
    # and measurement unit specified by object properties. The
    # measurement took place at the last update datetime. If needed
    # these measurements should be saved to a database or historian.

    lastMeasurement = None  # (1, 1)

    # LAST UPDATE
    # Datetime of the last meter reading. This time is used with
    # the measurement interval to determine when the meter should be
    # read.

    lastUpdate = datetime.utcnow()

    # MEASUREMENT INTERVAL
    # Constant time interval between readings. This and the last
    # measurement time are used to schedule the next meter reading.

    measurementInterval = timedelta(hours=1)

    # MEASUREMENT TYPE
    # See MeasurementType enumeration. Property being metered.

    measurementType = MeasurementType.Unknown

    # MEASUREMENT UNIT
    # See MeasurementUnit enumeration. Allowed units of measure. This
    # formulation is currently simplified by allowing only a limited
    # number of measurement units. These are not necessarily the raw
    # units; it should be the proper converted units.

    measurementUnit = MeasurementUnit.Unknown

    # NAME
    name = ''  # char

    def __index__(self):
        pass


    # FUNCTION READ_METER() - Read the meter point at scheduled intervals
    #
    # MeterPoints are updated on a schedule. Properties have been defined to
    # keep track of the time of the last update and the interval between
    # updates.
    #
    # While this seems easy, meters will be found to be diverse and may use
    # diverse standards and protocols. Create subclasses and redefine this
    # function as needed to handle unique conditions.
    def read_meter(self, obj):
        print('Made it to MeterPoint.read_meter() for ' + obj.name)


    # FUNCTION STORE() - Store last measurement into database or historian
    #
    # The default approach here could be to append a text record file. If the
    # file is reserved for one meterpoint, little or no metadata need be
    # repeated in records. Minimum content should be reading time and datum.
    #
    # Implementers will be found to have diverse practicies for databases and
    # historians.
    #
    # INPUTS:
    #   obj - MeterPoint object
    #
    # OUTPUTS:
    #   Updates database, file, or historian
    def store(self):
        print('Made it to store() function in ' + self.name + ' targeting database ' + self.dataFile)

        # Open a simple text file for appending
        # Append the formatted, paired last measurement time and its datum
        with open(self.dataFile, "a") as myfile:
            myfile.write("{},{};".format(format_ts(self.lastUpdate), self.lastMeasurement))
