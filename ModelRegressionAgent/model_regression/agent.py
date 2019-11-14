# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2019, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import os
import sys
import logging
from datetime import datetime as dt, timedelta as td
from dateutil import parser

import json
from scipy.optimize import lsq_linear
from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)
from volttron.platform.scheduling import cron, periodic
from volttron.platform.messaging import topics

import numpy as np
import pandas as pd
import patsy

from pandas.tseries.offsets import CustomBusinessDay
from pandas.tseries.holiday import USFederalHolidayCalendar as calendar
import scipy
import pytz
import re

utils.setup_logging()
_log = logging.getLogger(__name__)
UTC_TZ = pytz.timezone('UTC')
WORKING_DIR = os.getcwd()
__version__ = 0.1


class UpdatingAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(UpdatingAgent, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.site = config.get('campus', '')
        self.building = config.get('building', '')
        self.unit = config.get('unit', '')
        self.subdevices = config.get('subdevices')
        self.data_source = config.get('data_source', 'crate.prod')
        self.device_points = config.get('device_points')
        self.subdevice_points = config.get('subdevice_points')
        self.post_processing = config.get('post_processing')
        if self.device_points is None:
            _log.warn('Missing device points in config')
        if self.subdevice_points is None:
            _log.warn('Missing subdevice points in config')

        self.device = self.unit
        if self.device == '':
            _log.exception('Missing main device in config')

        self.aggregate_in_min = 1
        self.aggregate_freq = str(self.aggregate_in_min) + 'Min'

        self.training_schedule = int(config.get('training_schedule', 86400))
        self.seconds_in_past = int(config.get('seconds_in_past', 86400))

        self.model_struc = config.get('model_structure')
        self.model_depen = config.get('model_dependent')
        self.model_indepen = config.get('model_independent')
        if self.model_struc is None or self.model_depen is None or self.model_indepen is None:
            _log.exception('At least one of the model fields is missing in config')

        self.periodic_count = 0
        self.date_format = '%Y-%m-%d %H:%M:%S'
        run_onstart = config.get("run_onstart", False)
        if run_onstart:
            self.wait_time = 0
        else:
            self.wait_time = int(config.get('wait_time', 10))

        self.one_shot = config.get("one_shot", False)

        self.local_tz = pytz.timezone(config.get('local_tz', 'US/Pacific'))
        # If one shot is true then start and end should be specified
        if self.one_shot:
            self.start = config.get("start")
            self.end = config.get("end")
        self.aggregate_hourly = config.get("aggregate_hourly", False)
        self.file_dict = {}

        self.indepen_names = {}
        for key, value in self.model_indepen.items():
            self.indepen_names.update({key: self.model_indepen[key]['coefficient_name']})
            if 'lower_bound' not in self.model_indepen[key].keys():
                self.model_indepen[key].update({'lower_bound': '-infinity'})
                _log.debug('Filling in -infinity for missing lower bound for coefficient *{}*'.format(key))
            if 'upper_bound' not in self.model_indepen[key].keys():
                self.model_indepen[key].update({'upper_bound': 'infinity'})
                _log.debug('Filling in infinity for missing upper bound for coefficient *{}*'.format(key))

        if self.post_processing is not None:
            validate = self.validate_post_processor()
            if not validate:
                _log.warn("Post processing misconfigured! Agent will not attempt post-processing")
                self.post_processing = None

        self.input_data = {}
        if self.subdevices:
            for subdevice in self.subdevices:
                inner_dict = {}
                for map, point in self.subdevice_points.items():
                    topic = topics.RPC_DEVICE_PATH(campus=self.site,
                                                   building=self.building,
                                                   unit=self.device,
                                                   path=subdevice,
                                                   point=point)
                    inner_dict.update({map: topic})
                for map, point in self.device_points.items():
                    topic = topics.RPC_DEVICE_PATH(campus=self.site,
                                                   building=self.building,
                                                   unit=self.device,
                                                   path='',
                                                   point=point)
                    inner_dict.update({map: topic})
                self.input_data.update({subdevice: inner_dict})
        else:
            self.input_data[self.device] = {}
            for point in self.device_points:
                self.input_data[self.device][point] = topics.RPC_DEVICE_PATH(campus=self.site,
                                                                             building=self.building,
                                                                             unit=self.device,
                                                                             path='',
                                                                             point=point)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        if not self.one_shot:
            self.core.periodic(self.training_schedule, self.periodic_regression, wait=self.wait_time)
        else:
            try:
                self.start = parser.parse(self.start)
                self.start = self.local_tz.localize(self.start)
                self.end = parser.parse(self.end)
                self.end = self.local_tz.localize(self.end)
            except (NameError, ValueError) as e:
                _log.debug('One shot regression:  Start or end time not specified correctly!: *{}*'.format(e))
                self.end = dt.now(self.local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
                self.start = self.end - td(seconds=self.seconds_in_paste)
            self.rpc_start = self.start.astimezone(UTC_TZ)
            self.rpc_end = self.rpc_start + td(hours=1)
        self.get_data()

    @Core.receiver('onstop')
    def stop(self, sender, **kwargs):
        pass

    def periodic_regression(self):
        self.file_dict = {}
        self.end = dt.now(self.local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        self.start = self.end - td(seconds=self.seconds_in_past)
        self.rpc_start = self.start.astimezone(UTC_TZ)
        self.rpc_end = self.rpc_start + td(hours=1)
        self.get_data()

    def get_data(self):
        if not self.validate_config():
            _log.error('Config. file is not valid, exiting...')
            return

        # set up initial start and end times
        self.periodic_count += 1
        self.exec_start = utils.get_aware_utc_now()

        _log.debug('Start regression localtime: {} - UTC converted: {}'.format(self.start, self.start.astimezone(pytz.UTC)))
        _log.debug('End regression localtime: {} - UTC converted: {}'.format(self.end, self.end.astimezone(pytz.UTC)))

        # iterate for each subdevice
        for key1, value_dict in self.input_data.items():
            agg_df = None
            if self.start.tzinfo is None or self.start.tzinfo.utcoffset(self.start) is None:  # datetime is naive
                self.rpc_start = self.local_tz.localize(self.start).astimezone(UTC_TZ)
                self.rpc_end = self.rpc_start + td(hours=1)
            else:
                self.rpc_start = self.start.astimezone(UTC_TZ)
                self.rpc_end = self.rpc_start + td(hours=1)

            while self.rpc_start < self.end.astimezone(pytz.UTC):

                # handle weekends
                if self.rpc_start.astimezone(self.local_tz).weekday() > 4:
                    self.rpc_start = self.rpc_start + td(hours=1)
                    self.rpc_end = self.rpc_start + td(hours=1)
                    continue

                df = None
                # get data via query to historian
                for key2, value in value_dict.items():
                    rpc_start_str = self.rpc_start.strftime(self.date_format)
                    rpc_end_str = self.rpc_end.strftime(self.date_format)
                    result = self.vip.rpc.call(self.data_source,
                                               'query',
                                               topic=value,
                                               start=rpc_start_str,
                                               end=rpc_end_str,
                                               order='LAST_TO_FIRST',
                                               external_platform='volttron collector').get(timeout=300)
                    _log.debug(result)
                    if not bool(result['values']):
                        _log.debug('ERROR: empty RPC return for coefficient *{}* at {}'.format(key2, self.rpc_start))
                        continue
                    df2 = pd.DataFrame(result['values'], columns=['Date', key2])
                    df2['Date'] = pd.to_datetime(df2['Date'])

                    # Check with Sen if he is using this on updated RTU model
                    if self.aggregate_hourly:
                        df2 = df2.groupby([pd.Grouper(key='Date', freq='h')]).mean()
                    else:
                        df2 = df2.groupby([pd.Grouper(key='Date', freq=self.aggregate_freq)]).mean()
                    df = df2 if df is None else pd.merge(df, df2, how='outer', left_index=True, right_index=True)
                    _log.debug(df)

                if agg_df is None:
                    agg_df = df
                else:
                    agg_df = agg_df.append(df)
                _log.debug('aggregate dataframe:')
                _log.debug(agg_df)

                # increment by hour
                self.rpc_start = self.rpc_start + td(hours=1)
                self.rpc_end = self.rpc_start + td(hours=1)  #

            _log.debug('outputting dataframe:')
            _log.debug(agg_df)
            filename = '{}/data/{}-{} - {}.csv'.format(WORKING_DIR, self.start, self.end, key1)
            self.file_dict[key1] = filename
            try:
                with open(filename, 'w+') as outfile:
                    agg_df.to_csv(outfile, mode='a', index=True)
                    _log.debug('*** finished outputting data ***')
            except Exception as e:
                _log.error('File output failed, check whether the dataframe is empty - {}'.format(e))

        # perform regression using data from each outputted file
        for device, input_file in self.file_dict.items():
            try:
                df = pd.read_csv(input_file)
                self.perform_regression(df, device)
            except Exception as e:
                _log.error('Failed to read and perform regression on file *{}* - {}'.format(input_file, e))

    def perform_regression(self, df, device):
        df = df.reset_index()
        df = df.drop(['index'], axis=1)

        holiday = CustomBusinessDay(calendar=calendar()).onOffset
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_convert(self.local_tz)
        match = df["Date"].map(holiday)
        df = df[match]

        # process the coefficients from data by hour
        out_df = None
        for i in range(24):
            hour_df = df.loc[df['Date'].dt.hour == i]
            _log.debug(hour_df)
            filename = '{}/data/{}-hourly-{}.csv'.format(WORKING_DIR, device, i)
            with open(filename, 'w+') as outfile:
                hour_df.to_csv(outfile, mode='a', index=True)
            coeffs, col_name_dict = self.calc_coeffs(hour_df)
            out = pd.Series()
            out = out.append(coeffs)
            out_columns = out.index
            out_values = out.values
            out_dict = {}
            for j in range(len(out_columns)):
                out_dict.update({out_columns[j]: [out_values[j]]})
            hour_out_df = pd.DataFrame.from_dict(out_dict)
            _log.debug('coefficients for hour {}'.format(str(i)))
            _log.debug(hour_out_df)
            if out_df is None:
                out_df = hour_out_df
            else:
                out_df = out_df.append(hour_out_df)

        # perform operations on columns
        out_df = out_df.rename(columns=col_name_dict)
        cols = out_df.columns.tolist()
        cols.sort()
        out_df = out_df[cols]
        if self.post_processing is not None:
            out_df = self.post_processor(out_df)

        _log.debug('outputting dataframe: ')
        _log.debug(out_df)
        with open('{}/results/{}.csv'.format(WORKING_DIR, device), 'w+') as outfile:
            out_df.to_csv(outfile, mode='a', index=False)
        out_df.reset_index()
        out_dict = out_df.to_dict(orient='list')
        with open('{}/results/{}.json'.format(WORKING_DIR, device), 'w+') as outfile:
            json.dump(out_dict, outfile, indent=4, separators=(',', ': '))
        _log.debug('***finished outputting coefficients***')

        exec_end = utils.get_aware_utc_now()
        exec_dif = exec_end - self.exec_start
        _log.debug('Execution start: {}, current time: {}, elapsed time: {}'.format(self.exec_start, exec_end, exec_dif))

    def calc_coeffs(self, df):
        spl = self.model_struc.split(' = ')
        formula = self.model_depen[0] + ' ~ ' + spl[1]

        df = df.dropna()
        paren_list = []
        paren_list = re.findall(r'\((.*?)\)', self.model_struc)
        model_indepen_alt = None
        model_indepen_alt = dict(self.indepen_names)

        # handle an expression in parentheses in model structure
        if paren_list:
            non_paren_list = []
            for key, value in self.indepen_names.items():
                if '(' not in key:
                    non_paren_list.append(key)
            count = 1
            for expr in paren_list:
                col_name = 'paren_' + str(count)
                formula = formula.replace(expr, col_name)
                paren_expression_name = '(' + expr + ')'
                val = self.indepen_names[paren_expression_name]
                model_indepen_alt.update({col_name: val})
                if paren_expression_name in model_indepen_alt:
                    del model_indepen_alt[paren_expression_name]
                paren_exp_list = expr.split(' ')  # space required
                if paren_exp_list[1] == '+':
                    df[col_name] = df[paren_exp_list[0]] + df[paren_exp_list[2]]
                elif paren_exp_list[1] == '-':
                    df[col_name] = df[paren_exp_list[0]] - df[paren_exp_list[2]]
                elif paren_exp_list[1] == '*':
                    df[col_name] = df[paren_exp_list[0]] * df[paren_exp_list[2]]
                elif paren_exp_list[1] == '/':
                    df[col_name] = df[paren_exp_list[0]] / df[paren_exp_list[2]]

                _log.debug(df)
                count += 1

            # remove column of point in parentheses if it's not being used on its own to avoid unwanted coefficients
            for expr in paren_list:
                paren_exp_list = expr.split(' ')
                if paren_exp_list[0] not in non_paren_list and paren_exp_list[0] in df.columns:
                    df = df.drop(columns=[paren_exp_list[0]])
                if paren_exp_list[2] not in non_paren_list and paren_exp_list[2] in df.columns:
                    df = df.drop(columns=[paren_exp_list[2]])

        if model_indepen_alt is None:
            model_indepen_alt = self.indepen_names

        if 'intercept' in self.model_indepen.keys():
            df['intercept'] = 1
        elif 'Intercept' in self.model_indepen.keys():
            df['Intercept'] = 1

        x = patsy.dmatrices(formula, df, return_type='dataframe')[1]
        _log.debug('formula: {0}'.format(formula))
        y = df[self.model_depen[0]]
        scipy_result = scipy.optimize.lsq_linear(x, y, bounds=self.bounds)
        _log.debug('\n***scipy regression: ***')
        _log.debug(scipy_result.x.tolist())
        keys = model_indepen_alt.keys()
        keys.sort()
        fit = pd.Series()
        i = 0
        for coeff in scipy_result.x.tolist():
            fit = fit.set_value(keys[i], coeff)
            i += 1

        return fit, model_indepen_alt

    def post_processor(self, df):
        rdf = pd.DataFrame()
        for key, value in self.post_processing.items():
            try:
                rdf[key] = df.eval(value)
            except:
                rdf[key] = df[key]
        return rdf

    def validate_post_processor(self):
        independent_coefficients = set(self.indepen_names.values())
        validate_coefficients = set()
        for coefficient, processor in self.post_processing.items():
            for key, name in self.indepen_names.items():
                if name in processor:
                    validate_coefficients.add(name)
                    break
        return validate_coefficients == independent_coefficients

    def validate_config(self):
        try:
            if self.site == '':
                _log.error('Missing campus in config')
                return False
            if self.building == '':
                _log.error('Missing building in config')
                return False
            if self.subdevices is None:
                _log.error('Missing list of subdevices in config')
                return False
            if len(set(self.subdevice_points.keys()).intersection(self.device_points.keys())) != 0:
                _log.error('The same point is included in both device_points and subdevice_points in config')
                return False

            spl = self.model_struc.split(' = ')
            formula = self.model_depen[0] + ' ~ ' + spl[1]

            # process bounds for each coefficient
            lower_bounds = ()
            upper_bounds = ()
            for key, value in self.model_indepen.items():
                if self.model_indepen[key]['lower_bound'] == 'infinity':
                    self.model_indepen[key]['lower_bound'] = np.inf
                elif self.model_indepen[key]['lower_bound'] == '-infinity':
                    self.model_indepen[key]['lower_bound'] = np.NINF
                if self.model_indepen[key]['upper_bound'] == 'infinity':
                    self.model_indepen[key]['upper_bound'] = np.inf
                elif self.model_indepen[key]['upper_bound'] == '-infinity':
                    self.model_indepen[key]['upper_bound'] = np.NINF

                try:
                    if self.model_indepen[key]['lower_bound'].replace('-', '').isdigit():
                        self.model_indepen[key]['lower_bound'] = int(self.model_indepen[key]['lower_bound'])
                except AttributeError as e:
                    _log.debug('Lower bound for *{}* is not a string, no need to try to set to int - {}'.format(key, e))

                try:
                    if self.model_indepen[key]['upper_bound'].replace('-', '').isdigit():
                        self.model_indepen[key]['upper_bound'] = int(self.model_indepen[key]['upper_bound'])
                except AttributeError as e:
                    _log.debug('Upper bound for *{}* is not a string, no need to try to set to int - {}'.format(key, e))

                lower_bounds += (self.model_indepen[key]['lower_bound'],)
                upper_bounds += (self.model_indepen[key]['upper_bound'],)
            self.bounds = (lower_bounds, upper_bounds)
            _log.debug('bounds: {0}'.format(self.bounds))

            formula_indep = spl[1]
            for key, value in self.model_indepen.items():
                if self.model_indepen[key]['lower_bound'] > self.model_indepen[key]['upper_bound']:
                    _log.error('Lower bound is greater than upper bound for coefficient *{}*'.format(key))
                    return False
                if key not in formula and key != 'intercept' and key != 'Intercept':
                    _log.error('Coefficient *{}* is not present in formula'.format(key))
                    return False
                if key in formula_indep:
                    formula_indep = formula_indep.replace(key, '')
            for char in formula_indep:
                if char != ' ' and char != '+' and char != '-':
                    _log.error('There is a coefficient in the formula not included in model_independent')
                    return False

        except Exception as e:
            _log.error('Unhandled exception when validating config. - *{}*'.format(e))
            return False
        return True


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(UpdatingAgent)
    except Exception as e:
        _log.exception('unhandled exception - {}'.format(e))


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
