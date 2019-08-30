
from datetime import timedelta

from information_service_model import InformationServiceModel
from measurement_type import MeasurementType
from measurement_unit import MeasurementUnit
from interval_value import IntervalValue


class TemperatureForecastModel(InformationServiceModel, object):

    # TemperatureForecastModel - manage local hourly temperature prediction
    # obtained from www.wunderground.com.
    def __init__(self):
        super(TemperatureForecastModel, self).__init__()
        ## Protected TemperatureForecastModel Properties
        self.zipCode = '99352'
        self.key = '3f10e7fb5368a34a'

        # TEMPERATUREFORECASTMODEL() - Constructs TemperatureForecastModel object
        # Forecasts local hourly temperature (DEGf) using Weather Underground
        # (wunderground.com).
        self.address = 'http://api.wunderground.com/api/'
        self.description = 'Weather Underground local one-day hourly temperature forecast'
        self.informationType = MeasurementType.Temperature
        self.informationUnits = MeasurementUnit.degF
        self.license = 'non-commercial Cumulus level'
        self.name = 'temperature_forecast'  # may be redefined
        #   NOTE: Function Hours() corrects behavior of Matlab's function hours().
        #self.nextScheduledUpdate = datetime(date) + Hours(hour(datetime)) + Hours(1)
        self.serviceExpirationDate = 'indeterminate'
        self.updateInterval = timedelta(hours=12)  # recommended, may be changed

    def update_information(self, mkt):
        # UPDATE_INFORMATION() - retrieve the local hourly temperature forecast
        # from www.wunderground.com and store the predicted temperatures as
        # interval values.
        # NOTE: there is probably no good reason to ever call this method more than
        # once every 3 hours, or so. It collects 36 hourly forecasts, so it might
        # be deferrable as much as 12 hours without losing its ability to assist
        # with day-ahead forecasts.

        # The format of the url inquiry
        url = ''.join([self.address, self.key, '/hourly/q/', self.zipCode, '.json'])


        #for ti in mkt.timeIntervals:
            #iv = IntervalValue(obj, ti(i), mkt, 'PredictedValue', value)  # an IntervalValue
            #self.predictedValues = [self.predictedValues, iv]

