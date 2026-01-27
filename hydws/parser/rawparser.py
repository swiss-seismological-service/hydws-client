import json
import logging

import pandas as pd

from hydws.parser import BoreholeHydraulics

# Water density at 20°C in kg/m³
WATER_DENSITY_KG_M3 = 998.2

# Gravitational acceleration in m/s²
GRAVITY_M_S2 = 9.81

# Allowed operations for unit conversion
ALLOWED_UNIT_OPERATIONS = {'mul', 'truediv', 'add', 'sub'}


class RawHydraulicsParser:

    def __init__(self,
                 config_path: str,
                 boreholes_metadata: list[dict]):
        """
        This class Parses data from a dataframe to HYDWS format. Uses
        transformations and mappings which are defined in a config file.

        :param config_path: Path to JSON config file defining column mappings.
        :param boreholes_metadata: List of dictionaries with borehole metadata.
        """
        self.logger = logging.getLogger(__name__)

        with open(config_path) as f:
            self.config = json.load(f)

        self.borehole_by_section_name = {}
        self.name_map = {}
        self.assign_to = {'plan': self._assign_to_plan,
                          'sectionID': self._assign_to_section}

        for borehole in boreholes_metadata:
            if 'sections' in borehole:
                for s in borehole['sections']:
                    self.name_map[s['name']] = s['publicid']
                    self.borehole_by_section_name[s['name']] = borehole

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

    def _apply_conditions(self, col_config: dict, df: pd.DataFrame):
        """
        Selects values from columns based on conditional rules.

        Iterates through conditions and uses mask() to selectively replace
        values in the result. Supports rules:
        - 'above': use value if it exceeds threshold
        - 'below': use value if it is below threshold
        - 'above-current': use value if (value - current) > threshold
        - 'below-current': use value if (current - value) > threshold

        This is useful for selecting between redundant sensors based on
        which one has valid/preferred readings.
        """
        results_column = pd.Series(0.0, index=df.index)

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
                raise ValueError(
                    f"Unknown condition rule: {condition['rule']}. "
                    f"Allowed: above, below, above-current, below-current")

            results_column.mask(
                logic, condition_column, inplace=True)

        return results_column

    def _assign_to_plan(
            self, boreholes: dict, col_config: dict, column: pd.DataFrame):
        with open(col_config['section'], 'r') as f:
            plan = pd.read_csv(f, sep=',', skipinitialspace=True)

        plan['date_from'] = pd.to_datetime(
            plan['date_from'], format='%Y/%m/%dT%H:%M:%S')
        plan['date_until'] = pd.to_datetime(
            plan['date_until'], format='%Y/%m/%dT%H:%M:%S')

        for row in plan.itertuples():
            period = column.sort_index()[row.date_from:row.date_until]
            if not period.empty:
                self._assign_to_section(
                    boreholes, col_config, period,
                    section_override=row.interval)

    def _assign_to_section(
            self, boreholes: dict, col_config: dict, column: pd.DataFrame,
            section_override: str | None = None):

        section_name = section_override or col_config['section']
        borehole_data = self.borehole_by_section_name[section_name]
        borehole_id = borehole_data['publicid']
        section_id = self.name_map[section_name]

        if 'unitConversion' in col_config:
            column = self._convert_unit(
                column,
                col_config['unitConversion'][0],
                col_config['unitConversion'][1])

        if (col_config.get('sensorPosition') == 'surface'
                and 'pressure' in column.columns[0]):
            column = self._convert_to_surface_measurement(
                column, section_name, borehole_data)

        if borehole_id not in boreholes:
            boreholes[borehole_id] = BoreholeHydraulics(borehole_data)

        # add hydraulic data to parser
        section = boreholes[borehole_id][section_id]
        section.hydraulics = pd.concat([section.hydraulics, column], axis=1)

    def _convert_unit(self, column: pd.DataFrame, operation: str, num: float):
        if operation not in ALLOWED_UNIT_OPERATIONS:
            raise ValueError(
                f"Unknown unit conversion operation: {operation}. "
                f"Allowed: {ALLOWED_UNIT_OPERATIONS}")
        return getattr(column, operation)(num)

    def _convert_to_surface_measurement(
            self, column: pd.DataFrame, section_name: str,
            borehole_data: dict):
        """
        Takes into account that pressure measurement was done on the surface.

        Adds the pressure of the water column to the measured values of
        toppressure and bottompressure.

        :param section_name: section for which pressure was measured at surface
        :param borehole_data: borehole metadata containing section info
        """
        # get correct section info
        sec_info = next(
            (item for item in borehole_data['sections']
                if item['name'] == section_name), None)

        if sec_info is None:
            raise ValueError(f"Section '{section_name}' not found in borehole")

        abs_depth = borehole_data['altitude']['value'] - \
            sec_info['bottomaltitude']['value']

        # calculate hydraulic pressure (P = ρgh)
        hydraulic_pressure = WATER_DENSITY_KG_M3 * GRAVITY_M_S2 * abs_depth

        return column + hydraulic_pressure
