import json
import logging
from copy import deepcopy

import pandas as pd

from hydws.parser import BoreholeHydraulics


class RawHydraulicsParser:

    def __init__(self,
                 config_path: str,
                 boreholes_metadata: list[dict]):
        """
        This class Parses data from a dataframe to HYDWS format. Uses
        transformations and mappings which are defined in a config file.

        :param config_path: Path to config file. If not provided it looks for
                            'CONFIG_PATH' environment variable.
        :param boreholes_metadata: List of dictionaries with borehole metadata.
        """
        self.logger = logging.getLogger(__name__)

        with open(config_path) as f:
            self.config = json.load(f)

        self.sections_map = {}
        self.name_map = {}
        self.assign_to = {'plan': self._assign_to_plan,
                          'sectionID': self._assign_to_section}

        for borehole in boreholes_metadata:
            if 'sections' in borehole:
                for s in borehole['sections']:
                    self.name_map[s['name']] = s['publicid']
                    self.sections_map[s['name']] = borehole

    def parse(self, data: pd.DataFrame, format='json') -> list | dict:
        """
        Parses the provided dataframe to hydws json according to the config.

        :param data: Dataframe with hydraulic samples data. Columns which are
                not present in the config file will be ignored.
        :param format: 'json' or 'hydwsparser'. JSON returns a list of dicts,
                hydwsparser returns a dictionary of HYDWSParser objects.
        """
        boreholes = {}

        for col_config in self.config:
            # select all columns which are referenced in config
            selection = data[data.columns.intersection(
                col_config['columnNames'])]

            # continue if columns not in dataframe
            if selection.empty:
                continue

            # depending on conditions specified or not sum or apply cond
            if 'conditions' in col_config:
                selection = self._apply_conditions(col_config, selection)
            else:
                selection = selection.sum(axis=1)

            # continue if sum or conditions return dataframe of zeroes
            if not selection.any():
                continue

            selection = pd.DataFrame(selection.rename(col_config['fieldName']))

            # use correct strategy to assign column to sections
            self.assign_to[col_config['assignTo']](
                boreholes, col_config, selection)

        if format == 'json':
            return [b.to_json() for b in boreholes.values()]
        elif format == 'hydwsparser':
            return boreholes
        else:
            raise KeyError('Return format unknown.')

    def _apply_conditions(self, col_config, df):

        results_column = df[df.columns.intersection(
            [col_config['columnNames'][0]])].sum(axis=1)
        results_column.values[:] = 0

        for condition in col_config['conditions']:

            condition_column = df[df.columns.intersection(
                condition['columnNames'])].sum(axis=1)

            if condition_column.empty:
                continue

            if condition['rule'] == 'above':
                logic = condition_column > condition['value']
            elif condition['rule'] == 'below':
                logic = condition_column < condition['value']
            elif condition['rule'] == 'above-current':
                logic = (condition_column
                         - results_column) > condition['value']
            elif condition['rule'] == 'below-current':
                logic = (results_column
                         - condition_column) > condition['value']
            else:
                self.logger.error('Condition rule unknown.')
                raise ValueError

            results_column.mask(
                logic, condition_column, inplace=True)

        return results_column

    def _assign_to_plan(
            self, boreholes: dict, col_config: dict, column: pd.DataFrame):
        with open(col_config['section'], 'r') as f:
            plan = pd.read_csv(f, sep=',', skipinitialspace=True)

        config = deepcopy(col_config)

        plan[['date_from', 'date_until']] = \
            plan[['date_from', 'date_until']].apply(
            pd.to_datetime, format='%Y/%m/%dT%H:%M:%S')

        for row in plan.iterrows():
            period = column.sort_index()[
                row[1]['date_from']:row[1]['date_until']]
            if not period.empty:
                config['section'] = row[1]['interval']
                self._assign_to_section(
                    boreholes, config, period)

    def _assign_to_section(
            self, boreholes: dict, col_config: dict, column: pd.DataFrame):

        borehole_data = self.sections_map[col_config['section']]

        if 'unitConversion' in col_config:
            column = self._convert_unit(
                column,
                col_config['unitConversion'][0],
                col_config['unitConversion'][1])

        if 'sensorPosition' in col_config and 'pressure' in column.columns[0]:
            if col_config['sensorPosition'] == 'surface':
                column = self._convert_to_surface_measurement(
                    column, col_config['section'], borehole_data)

        if not borehole_data['publicid'] in boreholes:
            boreholes[borehole_data['publicid']
                      ] = BoreholeHydraulics(borehole_data)

        # add hydraulic data to parser
        boreholes[borehole_data['publicid']
                  ][self.name_map[col_config['section']]].hydraulics = \
            pd.concat([
                boreholes[borehole_data['publicid']
                          ][self.name_map[col_config['section']]
                            ].hydraulics, column],
                      axis=1)

    def _convert_unit(self, column: pd.DataFrame, operation: str, num: float):
        return getattr(column, operation)(num)

    def _convert_to_surface_measurement(
            self, column: pd.DataFrame, section_id: str, borehole_data: dict):
        """
        Takes into account that pressure measurement was done on the surface.

        Adds the pressure of the water column to the measured values of
        toppressure and bottompressure.

        :param section_id: section for which pressure was measured at surface
        :param unit_factor: factor of the desired unit (eg 10^6 for MPa)
        """
        # get correct section info
        sec_info = next(
            (item for item in borehole_data['sections']
                if item['name'] == section_id), {})

        abs_depth = borehole_data['altitude']['value'] - \
            (sec_info['bottomaltitude']['value'])

        # calculate hydraulic pressure
        hydraulic_pressure = 998.2 * abs_depth * 9.81

        return column + hydraulic_pressure
