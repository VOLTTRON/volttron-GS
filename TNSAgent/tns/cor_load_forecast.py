# try:
#     from .local_asset_model import LocalAssetModel
#     from .time_interval import TimeInterval
#     from .meter_point import MeterPoint
#     from .market import Market
#     from .temperature_forecast_model import TemperatureForecastModel
# except:
#     from local_asset_model import LocalAssetModel
#     from time_interval import TimeInterval
#     from meter_point import MeterPoint
#     from market import Market
#     from temperature_forecast_model import TemperatureForecastModel
#
# from datetime import datetime, timedelta, date, time
# from dateutil import relativedelta
#
# import logging
# #utils.setup_logging()
# _log = logging.getLogger(__name__)
#
#
# class CorLoadForecast(LocalAssetModel):
#     # CORLOADFORECAST - a LocalAssetModel that predicts City of Richland load
#     def __init__(self):
#         averageMonthlyLoad = [  # tracked when there is no meter [avg.kW]
#                               - 100000,  # Jan
#                               - 100000,  # Feb
#                               - 100000,  # Mar
#                               - 100000,  # Apr
#                               - 100000,  # May
#                               - 100000,  # Jun
#                               - 100000,  # Jul
#                               - 100000,  # Aug
#                               - 100000,  # Sep
#                               - 100000,  # Oct
#                               - 100000,  # Nov
#                               - 100000]  # Dec
#         #       Daily peak load is initialized here, but it is also dynamically
#         #       updated.
#         peakByDay = -80000 * ones(31, 1)  # [peak hourly kW]
#         #       Peak daily temperature is initialized here, but it is also
#         #       dynamically updated.
#         peakTempByDay = 57 * ones(31, 1)  # [deg.F]
#         trackingGain = 1 / (24 * 14)  # gain of recursive tracking filter
#
#
#     def schedule_power(obj, mkt):
#         # SCHEDULE_POWER() - use a regression formula to predict City-of-Richland
#         # electric load up to 24 hours into the future. (See report Richland Load
#         # Model received from ZT Taylor.)
#         # NOTE: This load is not price-responsive.
#         # NOTE: This method should be called about once every hour. It does not
#         # make sense to do so more often because the predictions are not especially
#         # dynamic.
#         #
#         # Regression inputs:
#         # - forecast temperature (including current and predicted high temperature)
#         # - current load (with or without corresponding metering)
#         # - historical peak load on this day type (metered or modeled)
#         # - a set of four regression coefficients from lookup table
#         # - a tracking gain, if metered data is unavailable
#
#         #   Get the active time intervals and make sure they are chronologically
#         #   sorted.
#         time_interval = mkt.timeIntervals
#         [~, index] = sort([time_interval.startTime])
#         time_interval = time_interval(index)
#
#         #   Read (if metered) or model (if inferred) the current load Load_t.
#         #   Look for an appropriate MeterPoint meter.
#         meter_point = findobj(obj.meterPoints, 'MeasurementType', ...
#         MeasurementType('power_real'))
#
#         if isempty(meter_point)
#
#             #       No appropriate load meter is found. The current load Load_t must be
#             #       modeled or inferred from the current scheduled power and a tracking
#             #       of average load.
#             #       Start by getting the currently scheduled load (i.e., in time
#             #       interval ti(1).
#             scheduled_power = findobj(obj.scheduledPowers, 'timeInterval', ...
#             time_interval(1))  # an IntervalValue
#
#             if isempty(scheduled_power):
#                 scheduled_power = obj.defaultPower
#             else:
#                 scheduled_power = scheduled_power.value
#                 # currently scheduled electrical load [avg.kW]
#
#             #       This filter nudges the current load values nearer to the average
#             #       load over time.
#             index = month(time_interval(1).startTime)
#             Load_t = (scheduled_power + obj.trackingGain * ...
#             obj.averageMonthlyLoad(index)) ...
#             / (1 + obj.trackingGain)  # [avg.kW]
#
#         else:
#
#             # An appropriate meter object mp was found. Read its current
#             #       measurement to learn current Load_t.
#             Load_t = meter_point.currentMeasurement  # [kW]
#
#         end  # if isempty(mp)
#
#         #   Find the peak load and peak temperature from the last day of this type
#         #   (i.e., the same weekday last week). Property peakByDay provides a
#         #   rolling lookup for these values.
#         index = day(time_interval(1).startTime - days(7))
#
#         T_max_pdt = obj.peakTempByDay(index)
#
#         try
#             Peak_pdt = obj.peakByDay(index)  # [avg.kW]
#
#         catch
#         #       In case an array of peak demands has not been assembled yet, ...
#         Peak_pdt = obj.averageMonthlyLoad(month(ti(1).startTime))
#         end
#
#         #   Index through the active time intervals.
#         for i = 1:length(time_interval)
#
#             #       Extract categorical property Weekday from the time interval.
#             W = weekday(time_interval(i).startTime)
#
#             #       Extract categorical property H (hour) from the time interval.
#             #       NOTE: Add 1 to the hour H because the table is based on hour end.
#             #       Indexing is proper if range is [1,24], not [0,23].
#             H = hour(time_interval(i).startTime) + 1
#
#             #       Get the predicted Fahrenheit temperature for the time interval.
#             #       First look for an appropriate information service model.
#             information_service_model = findobj(obj.informationServiceModels{:}, 'informationType', MeasurementType('temperature'))
#
#             if isempty(information_service_model)
#
#                 #           No appropriate InformationServiceModel was found. Warn. The
#                 #           default power must be used.
#                 _log.warning['No appropriate temperature forecast service was ', ...
#                          'found for ', obj.name])
#
#                 #           Use a default value for scheduled power sp.
#                 Load_N = obj.defaultPower  # [avg.kW]
#
#             else:
#
#                 #           An appropriate InfromationServiceModel was found for
#                 #           temperature T_N.
#
#                 #           Get the predicted hourly temperatures.
#                 predicted_temperatures = ...
#                 [information_service_model(1).predictedValues.value]
#
#                 # Predict the maximum temperature today.                                                                  # [deg.F]
#                 T_max_today = max(predicted_temperatures)
#                 # maximum day temperature [deg.F]
#
#                 #           Pick out the temperature T_n in the indexed time interval.
#                 T_n = findobj(information_service_model(1).predictedValues, ...
#                 'timeInterval', time_interval(i))  # an IntervalValue
#                 #           And extract its value.
#                 T_n = T_n(1).value  # predicted temperature [deg.F]
#
#                 #           Under certain conditions, a NaN temperature value is generated.
#                 #           If so, use the average of the predicted temperatures.
#                 if isnan(T_n)
#                     T_n = mean(predicted_temperatures, 'omitnan')
#                 end
#
#                 #           Save the current temperature T_now. It is needed later.
#                 if i == 1:
#                     T_now = T_n
#
#                 #           Determine categorical input Mode from the predicted temperature.
#                 #           See report "Richland Load Model," Section 1.3.
#                 if T_n <= 56.6:
#                     Mode = 1  # "Heating" mode
#                 elif:
#                     T_n >= 69.4
#                     Mode = 3  # "High Cooling" mode
#                 else:
#                     Mode = 2  # "Moderate Cooling" mode
#
#                 #           Lookup the regression coefficients alpha, betta, gamma, and
#                 #           delta for the corresponding categorical variables Mode,
#                 #           Weekday, and Hour.
#                 #           NOTE: Static method make_table() is available to help create
#                 #           this table. The row indexing may be reviewed there.
#                 T = readtable('CorLoadModel.txt')
#
#                 #           Perform row indexing based on categorical columns.
#                 #           Mode {1:Heating 2: Moderate Cooling 3: High Cooling}
#                 Row = uint16(168 * (Mode - 1))
#                 Row = uint16(Row + 24 * (W - 1))  # W = Weekdays
#                 Row = uint16(Row + H)  # H = hour ending
#
#                 #           Extract the set of four regression coefficients.
#                 if ~isinteger(Row) | | Row < 1
#                     _log.warning'Row is not a pos. integer: #i', Row)
#
#                 Alpha = T{Row, 'Alpha'}
#                 Betta = T{Row, 'Betta'}
#                 Gamma = T{Row, 'Gamma'}
#                 Delta = T{Row, 'Delta'}
#
#                 #           Use the regression formula to predict Load_N in the indexed
#                 #           time interval.
#                 Load_N = Alpha * T_n ** 2
#                                        + Betta * (Peak_pdt * (T_max_today - T_max_pdt))
#                                        + Gamma * Load_t
#                                        + Delta * (T_n - T_now)  # [avg.kW]
#
#             #       Check whether a scheduled power exists in the indexed time
#             #       interval.
#             interval_value = findobj(obj.scheduledPowers, 'timeInterval', ...
#             time_interval(i))  # a TimeInterval?
#
#             if isempty(interval_value)
#
#                 #           No scheduled power was found in the indexed time interval.
#                 #           Create one and store it.
#                 interval_value = IntervalValue(obj, time_interval(i), mkt, ...
#                 'ScheduledPower', Load_N)
#                 obj.scheduledPowers = [obj.scheduledPowers, interval_value]
#
#             else
#
#                 #           A scheduled power was found in the indexed time interval.
#                 #           Simply reassign its value.
#                 interval_value.value = Load_N
#
#         end  # for i = 1:length(ti)
#
#         #   Update the daily peak load peak temperatures
#         Day = day(time_interval(1).startTime)
#         if hour(time_interval(1).startTime) == 0
#             obj.peakByDay(Day) = 0
#             obj.peakTempByDay(Day) = 0
#         else
#             #       NOTE: "Peak" load is the greatest NEGATIVE number, so it is a
#             #       minimum.
#             obj.peakByDay(Day) = min([Load_t, obj.peakByDay(Day)])
#             obj.peakTempByDay(Day) = max(T_now, obj.peakTempByDay(Day))
#         end
#
#
#     @classmethod
#     def make_table(cls):
#
#         # Three or four categorical inputs:
#         # These keys are available for the interpretation of the integer
#         # assignments to the categorical properties:
#         Mode_key = ["Heating", "Moderate Cooling", "High Cooling"]
#         # Weekday = ["Sat","Sun","Mon","Tue","Wed","Thu","Fri"]
#         [~, Weekday_key] = weekday(1:7)
#         Hour_key = 1:24
#
#         #   Assemble a lookup table
#         #   The first three columns are for the categorical indices:
#         Mode = [ones(168, 1)2 * ones(168, 1)3 * ones(168, 1)]
#         Weekday = [ones(72, 1)2 * ones(72, 1)3 * ones(72, 1)...
#                    4 * ones(72, 1)5 * ones(72, 1)6 * ones(72, 1)7 * ones(72, 1)]
#         Hour = [1:24]'
#         Hour = repmat(Hour, 21, 1)
#
#         #   The last four columns are for the regression coefficients that
#         #   correspond to the categorical inputs in the same row.
#
#         #   Alpha is the coefficient of squared temperature. I can't guess this
#         #   term, so assigning as zero.
#         Alpha = zeros(504, 1)
#
#         #   Betta is the coefficient of a term that uses peak electric load from a
#         #   previos day of the same type and the difference between the two days'
#         #   peak temperatures.
#         Betta = zeros(504, 1)
#
#         #   Gamma is the weighting of the current electrical load, which should be
#         #   very close to one. Use one until detailed factors are delivered.
#         Gamma = ones(504, 1)
#
#         #   Delta is the factor of temperature change. This is estimated for now by
#         #   multiplying reasonable residential factors by a scaling factor.
#         Delta = 40000 * [-0.115 * ones(168, 1)...  # "Heating"
#                          0.5 * 0.00137 * ones(168, 1)...  # "Moderate Cooling"
#                          0.00137 * ones(168, 1)]  # "High Cooling"
#
#         #   Create and save the lookup table.
#         T = table(Mode, Weekday, Hour, Alpha, Betta, Gamma, Delta)
#         writetable(T, 'CorLoadModel.txt')
#
#         # NOTE: This will need revision when a detailed model is received in the
#         # form of one or more lookup tables.
#
#     @classmethod
#     def test_all(cls):
#         # TEST_ALL() - test all the CorLoadForecast methods
#         print('Running CorLoadForecast.test_all()')
#         CorLoadForecast.test_schedule_power()
#
#     @classmethod
#     def test_schedule_power(cls):
#         # TEST_SCHEDULE_POWER() - test method schedule_power()
#         print('Running CorLoadForecast.test_schedule_power()')
#         pf = 'pass'
#
#         print('CAUTION: This tests that reasonable power values are created.')
#         print('         It does not rigorously test the prediction algorithm.')
#
#         #   Create a test market.
#         test_mkt = Market
#
#         #   Create and store a couple time intervals.
#         dt = datetime.now()
#         at = dt
#         dur = timedelta(hours=1)
#         mkt = test_mkt
#         mct = dt
#         st = dt
#         time_intervals = []
#         time_intervals[0] = TimeInterval(at, dur, mkt, mct, st)
#         st = st + dur
#         time_intervals[1] = TimeInterval(at, dur, mkt, mct, st)
#         test_mkt.timeIntervals = time_intervals
#
#         #   Create a test object.
#         test_obj = CorLoadForecast
#         test_obj.defaultPower = 30000
#
#         #   Create a and store a test information service model to provide future temperature.
#         test_ism = TemperatureForecastModel()
#         test_ism.update_information(test_mkt)  # update the hourly temperature prediction
#         # NOTE: list InformationServiceModels as cell array.
#         test_obj.informationServiceModels = {test_ism}
#
#         #   Create and store a meter point for the current load measurement.
#         test_mtr = MeterPoint()
#         test_mtr.measurementType = 'real_power'
#         test_mtr.currentMeasurement = 50000  # [avg.kW]
#
#         #   Run the test
#         try:
#             test_obj.schedule_power(test_mkt)
#             print('- the test ran to completion')
#         except:
#             pf = 'fail'
#             _log.warning'- the method encountered errors and stopped')
#
#
#         if len(test_obj.scheduledPowers) != 2:
#             pf = 'fail'
#             _log.warning('- the wrong number of scheduled powers was stored')
#         else:
#             print('- the right number of scheduled powers was stored')
#
#         if
#
#
#             any([test_obj.scheduledPowers.value] > 150000) or any([test_obj.scheduledPowers.value] < 20000):
#             pf = 'fail'
#             _log.warning'- the scheduled power values were not reasonable')
#         else:
#             print('- the scheduled power values were reasonable')
#
#         #   Success
#         print('- the test ran to completion')
#         print('Result: #s\n\n', pf)
#
#
