import logging
import uuid
from collections.abc import MutableMapping
from copy import deepcopy
from datetime import datetime

import pandas as pd
from hydws.parser.schema import (BoreholeSchema, SectionSchema,
                                 list_hydraulics_fields)


def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


def as_uuid(val):
    if isinstance(val, uuid.UUID):
        return val
    elif isinstance(val, str) and is_valid_uuid(val):
        return uuid.UUID(val)
    else:
        return uuid.UUID(val)


def create_value(value):
    return {'value': value}


def empty_section_metadata():
    return {
        'publicid': uuid.uuid4(),
        'name': 'Unnamed Section',
        'toplongitude': create_value(0),
        'toplatitude': create_value(0),
        'topaltitude': create_value(0),
        'bottomlongitude': create_value(0),
        'bottomlatitude': create_value(0),
        'bottomaltitude': create_value(-1),
        'topclosed': True,
        'bottomclosed': True,
    }


def empty_borehole_metadata():
    return {
        'publicid': uuid.uuid4(),
        'name': 'Unnamed Borehole',
        'longitude': create_value(0),
        'latitude': create_value(0),
        'altitude': create_value(0)
    }


class SectionHydraulics:
    def __init__(self, hydjson: dict = None):
        """
        Creates a SectionHydraulics object.

        Parameters
        ----------
        hydjson : dict, optional
            A dictionary containing the hydws-json of a section,
            by default None

        """
        self.metadata = empty_section_metadata()
        self._hydraulics = None

        if hydjson:
            self._from_json(hydjson)

    def _from_json(self, data: dict):
        """
        Loads hydws-json into the object.

        Parameters
        ----------
        data : dict
            A dictionary containing the hydws-json of a section
        """
        if 'hydraulics' not in data:
            data['hydraulics'] = []

        self.load_hydraulic_json(data['hydraulics'])

        self.metadata = {k: v for k, v in data.items() if k != 'hydraulics'}

        SectionSchema.model_validate(self.metadata)

    @classmethod
    def _load_hydraulic_json(cls, data: list[dict]):
        """
        Loads hydws-json of hydraulics into the object.

        Parameters
        ----------
        data : dict
            A dictionary containing the hydws-json of hydraulics

        Returns
        -------
        pd.DataFrame
            A dataframe containing the hydraulic data
        """
        if data is None or len(data) == 0:
            return pd.DataFrame()

        dataframe = pd.json_normalize(data, sep='_')

        dataframe.columns = dataframe.columns.str.replace(
            "(_).*", "", regex=True)

        dataframe['datetime'] = pd.to_datetime(dataframe['datetime'])
        dataframe.set_index(['datetime'], inplace=True, drop=True)

        return dataframe

    def load_hydraulic_json(self, data: list[dict]):
        """
        Loads hydws-json of hydraulics into the object.

        Parameters
        ----------
        data : dict
            A dictionary containing the hydws-json of hydraulics
        """
        self.hydraulics = self._load_hydraulic_json(data)

    def query_datetime(self,
                       starttime: datetime | None = None,
                       endtime: datetime | None = None):

        obj = deepcopy(self)
        obj.hydraulics = obj.hydraulics.loc[
            (obj.hydraulics.index >= starttime if starttime else True)
            & (obj.hydraulics.index <= endtime if endtime else True)
        ]

        return obj

    @property
    def hydraulics(self):
        return self._hydraulics

    @hydraulics.setter
    def hydraulics(self, data: pd.DataFrame):
        self._validate_dataframe(data)
        data.sort_index(inplace=True)
        self._hydraulics = data

    def to_json(self):
        """
        Returns hydraulic data of a section as a list of json / dict objects

        : param section_id: ID of the section for which data is returned.
        : param date: Date from which on the hydraulic data is returned.
        """
        # create hydraulic samples from dataframe
        if len(self.hydraulics) == 0:
            samples = []
        else:
            self.hydraulics['datetime'] = self.hydraulics.index
            self.hydraulics['datetime'] = \
                self.hydraulics['datetime'].dt.strftime(
                    '%Y-%m-%dT%H:%M:%S')

            samples = [{k: {'value': v} for k, v in m.items()
                        if v == v and v is not None}
                       for m in self.hydraulics.to_dict('records')]

            self.hydraulics.drop(columns=['datetime'], inplace=True)

        hydjson = deepcopy(self.metadata)
        hydjson['publicid'] = str(hydjson['publicid'])
        hydjson['hydraulics'] = samples
        return hydjson

    def _validate_dataframe(self, dataframe: pd.DataFrame):
        hydraulic_fields = list_hydraulics_fields()
        if not all(col in hydraulic_fields for col in dataframe.columns):
            raise KeyError(
                f'Columns '
                f'{list(set(dataframe.columns) - set(hydraulic_fields))}'
                f' in hydraulic dataframe are not valid names. Must be one'
                f' of {hydraulic_fields}.')


class BoreholeHydraulics(MutableMapping):
    """
    Parses hydraulic data of a borehole between "dataframes" and "hydws-json".
    """

    def __init__(self, hydjson: dict | None = None) -> None:

        self.logger = logging.getLogger(__name__)
        self.__sections = {}
        self.metadata = {}
        self.nloc = {}

        if hydjson is None:
            self.metadata = empty_borehole_metadata()
        else:
            self._from_json(hydjson)

    def query_datetime(self,
                       starttime: datetime | None = None,
                       endtime: datetime | None = None):
        obj = BoreholeHydraulics()
        obj.metadata = deepcopy(self.metadata)

        for key, section in self.__sections.items():
            obj[key] = section.query_datetime(starttime, endtime)

        return obj

    def _from_json(self, data: dict):
        sections = data['sections']

        self.metadata = {k: v for k, v in data.items() if k != 'sections'}
        BoreholeSchema.model_validate(self.metadata)
        for section_json in sections:
            section = SectionHydraulics(section_json)
            self[section.metadata['publicid']] = section

    def add_emtpy_section(self):
        section = SectionHydraulics()
        self[section.metadata['publicid']] = section
        return section.metadata['publicid']

    def section_from_json(self, data: dict):
        section = SectionHydraulics(data)
        self[section.metadata['publicid']] = section
        return section.metadata['publicid']

    def section_from_dataframe(self, data: pd.DataFrame):
        section = SectionHydraulics()
        section.hydraulics = data
        self[section.metadata['publicid']] = section

        return section.metadata['publicid']

    def __getitem__(self, key):
        return self.__sections[as_uuid(key)]

    def __setitem__(self, key, value):
        if isinstance(value, SectionHydraulics):
            self.__sections[as_uuid(key)] = value
            if 'name' in value.metadata:
                self.nloc[value.metadata['name']
                          ] = self.__sections[as_uuid(key)]

    def __delitem__(self, key):
        if 'name' in self.__sections[as_uuid(key)].metadata:
            del self.nloc[self.__sections[as_uuid(key)].metadata['name']]
        del self.__sections[as_uuid(key)]

    def __iter__(self):
        return iter(self.__sections)

    def __len__(self):
        return len(self.__sections)

    def __contains__(self, key):
        return key in self.__sections

    def __repr__(self):
        return f'<HYDWSParser: {repr(self.__sections)}>'

    def to_json(self):
        """
        Returns hydraulic data of a borehole as a json / dict object
        """
        hydjson = deepcopy(self.metadata)
        hydjson['publicid'] = str(hydjson['publicid'])
        hydjson['sections'] = [section.to_json()
                               for section in self.__sections.values()]
        return hydjson
