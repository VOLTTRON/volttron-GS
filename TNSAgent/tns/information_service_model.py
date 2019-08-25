
from datetime import timedelta

from measurement_type import MeasurementType
from measurement_unit import MeasurementUnit
from interval_value import IntervalValue


class InformationServiceModel:
    # InformationServiceModel Base Class
    # An InformationServiceModel manages an InformationService and predicts or
    # interpolates the information it provides.

    def __init__(self):
        # InformationService
        self.address = ''  # perhaps a web address storage
        self.description = ''
        self.informationType = MeasurementType.Unknown
        self.informationUnits = MeasurementUnit.Unknown
        self.license = ''
        self.nextQueryTime = None  # datetime.empty
        self.serviceExpirationDate = None  # datetime.empty
        self.updatePeriod = timedelta(hours=1)  # [h]

        # InformationServiceModel properties
        self.file = ''  # filename having entries for time intervals
        self.name = ''
        self.nextScheduledUpdate = None  # datetime.empty
        self.predictedValues = []  # IntervalValue.empty
        self.updateInterval = timedelta(hours=1)  # [h]


    # This template is available to conduct the forecasting of useful
    # information.
    @classmethod
    def update_information(ism, mkt):
        #   Gather active time intervals ti
        ti = mkt.timeIntervals

        #   index through active time intervals ti
        for i in range(len(ti)):  # for i = 1:length(ti)
            #       Get the start time for the indexed time interval
            st = ti(i).startTime

            #       Extract the starting time hour
            hr = st.hour

            #       Look up the value in a table. NOTE: tables may be used during
            #       development until active information services are developed.
            # Is the purpose of this one to read MODERATE weather temperature? YES
            T = readtable(ism.file)
            value = T(hr + 1, 1)

            #       Check whether the information exists in the indexed time interval
            # Question: what is ism? InformationServiceModel doesn't have 'values' as well as 'iv' properties.
            #   Suggestion: use long name as much as possible
            #   Need an example on what this one does. Really need a unit test here?
            #iv = findobj(ism.values, 'timeInterval', ti(i))
            iv = [x for x in ism.values if x.timeInterval == ti[i]]  #
            iv = iv[0] if len(iv)>0 else None

            if iv is None:  # isempty(iv):
                # The value does not exist in the indexed time interval. Create it and store it.
                #iv = IntervalValue(ism, ti(i), mkt, 'Temperature', value)
                iv = IntervalValue(ism, ti[i], mkt, MeasurementType.Temperature, value)
                ism.values = [ism.values, iv]

            else:
                # The value exists in the indexed time interval. Simply reassign it
                iv.value = value

    # Not sure when to use this yet
    #events
    #    UpdatedInformationReceived


if __name__ == '__main__':
    pass
