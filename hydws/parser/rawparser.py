import json
import logging
from copy import deepcopy

import numpy as np
import pandas as pd

from hydws.coordinates import CoordinateTransformer
from hydws.parser import HYDJSONParser


def calculate_coords(d: float, trajectory: pd.DataFrame, cols: list) -> tuple:
    """
    Calculate coordinates at depth d along trajectory.

    :param d: depth at which coordinates are requested
    :param trajectory: dataframe with the trajectory
    :param cols: names of columns in which the trajectory is saved, expects
                 [depth, northing, easting, elevation]
    """
    # check if exact depth can be found
    row = trajectory.loc[trajectory[cols[0]] == d]
    if not row.empty:
        x, y, z = row.iloc[0][cols[1:]]
    # if not, interpolate between two closest depths
    else:
        df_sort = trajectory.iloc[(
            trajectory[cols[0]] - d).abs().argsort()[:2]]
        d0, x0, y0, z0 = df_sort.iloc[0][cols]  # next larger
        d1, x1, y1, z1 = df_sort.iloc[1][cols]  # next smaller

        # interpolate elevation
        z = (d - d0) / (d1 - d0) * (z1 - z0) + z0

        # interpolate x and y using absolute z
        x = np.interp(z, (z0, z1), (x0, x1))
        y = np.interp(z, (z0, z1), (y0, y1))
    return x, y, z


def hydws_metadata_from_configs(borehole_publicid: str,
                                origin: list,
                                local_crs: str,
                                boreholes_path: str,
                                sections_path: str,
                                trajectory_path: str) -> dict:
    """
    Calculate borehole metadata in json format from raw csv files.

    :param origin: origin of coordinates in csv files, Easting, Northing, Elev.
    :param local_crs: CRS of coordinates in csv files.
    :param boreholes_path: path of csv with borehole information.
    :param sections_path: path of csv with sections information.
    :param trajectories_folder: Path of folder to trajectory files.
                Required column names are: 'depth', 'x', 'y', 'z'. Naming
                convention of files 'trajectory_{borehole}.csv'
    """

    # read configs
    boreholes_csv = pd.read_csv(boreholes_path)
    sections_csv = pd.read_csv(sections_path)

    boreholes_csv = boreholes_csv.loc[
        boreholes_csv['publicid'] == borehole_publicid]

    not_real_quantities = [
        'publicid',
        'topclosed',
        'bottomclosed',
        'description',
        'name',
        'location',
        'institution']

    transformer = CoordinateTransformer(local_crs, origin[0], origin[1])

    # transform local mouth coordinates to world coordinates
    boreholes_csv[['longitude', 'latitude', 'altitude']] = pd.Series(
        transformer.from_local_coords(
            *boreholes_csv[['x', 'y', 'z']].T.values)
    )
    boreholes_csv.drop(['x', 'y', 'z'], axis=1, inplace=True)

    # add value subkey where necessary
    for col in boreholes_csv.columns:
        if col not in not_real_quantities:
            boreholes_csv[col] = boreholes_csv[col].map(
                lambda x: {'value': x}, na_action='ignore')

    # convert to dict
    borehole = [{k: v for k, v in m.items() if pd.notnull(v)}
                for m in boreholes_csv.to_dict(orient='records')][0]

    section_df = sections_csv.loc[sections_csv['borehole']
                                  == borehole_publicid]
    if not section_df.empty:
        # get the correct trajectory
        trajectory = pd.read_csv(trajectory_path, index_col=0)

        # coordinate calculations need to be done for top and bottom
        for field in ['top', 'bottom']:
            # calculate coordinates from measureddepth
            coordinates = section_df[f'{field}measureddepth'] \
                .apply(calculate_coords,
                       args=(trajectory, ['depth', 'x', 'y', 'z'],)) \
                .apply(pd.Series)

            # transform into wgs84
            coordinates = pd.DataFrame(transformer.from_local_coords(
                coordinates[0], coordinates[1], coordinates[2])).T

            # update dataframe axes
            coordinates.columns = [
                f'{field}longitude',
                f'{field}latitude',
                f'{field}altitude']
            coordinates.index = section_df.index

            # append to group
            section_df = pd.concat([section_df, coordinates], axis=1)

        # create value dict from columns
        for col in section_df.columns:
            if col not in not_real_quantities:
                section_df[col] = section_df[col].map(
                    lambda x: {'value': x}, na_action='ignore')

        # convert to array of dicts
        sections = [{k: v for k, v in m.items() if pd.notnull(v)}
                    for m in section_df.drop(columns=['borehole']
                                             ).to_dict(orient='records')]
    else:
        sections = []

    # append to borehole
    borehole['sections'] = sections

    return borehole


class RawHydraulicsParser:

    def __init__(self,
                 config_path: str,
                 origin: list,
                 local_crs: str,
                 boreholes_path: str,
                 sections_path: str,
                 trajectories: dict):
        """
        This class Parses data from a dataframe to HYDWS format. Uses
        transformations and mappings which are defined in a config file.

        :param config_path: Path to config file. If not provided it looks for
                            'CONFIG_PATH' environment variable.
        """
        self.logger = logging.getLogger(__name__)

        with open(config_path) as f:
            self.config = json.load(f)

        self.sections_map = {}
        self.name_map = {}
        self.assign_to = {'plan': self._assign_to_plan,
                          'sectionID': self._assign_to_section}

        for _, row in pd.read_csv(boreholes_path).iterrows():
            metadata = hydws_metadata_from_configs(row['publicid'],
                                                   origin,
                                                   local_crs,
                                                   boreholes_path,
                                                   sections_path,
                                                   trajectories[row['name']])
            if 'sections' in metadata:
                for s in metadata['sections']:
                    self.name_map[s['name']] = s['publicid']
                    self.sections_map[s['publicid']] = metadata

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
            return [b.get_borehole_json() for b in boreholes.values()]
        elif format == 'hydwsparser':
            return boreholes
        else:
            raise KeyError('Return format unknown.')

    def _apply_conditions(self, col_config, df):

        results_column = df[df.columns.intersection(
            [col_config['columnNames'][0]])].copy().sum(axis=1)
        results_column.values[:] = 0

        for condition in col_config['conditions']:

            condition_column = df[df.columns.intersection(
                condition['columnNames'])].copy().sum(axis=1)

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

        borehole_data = self.sections_map[self.name_map[col_config['section']]]

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
            boreholes[borehole_data['publicid']] = HYDJSONParser(borehole_data)

        # add hydraulic data to parser
        boreholes[borehole_data['publicid']].load_hydraulics_dataframe(
            self.name_map[col_config['section']], column, merge=True)

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
