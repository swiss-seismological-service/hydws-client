import json
import os
import uuid
from copy import deepcopy
from datetime import datetime

import pandas as pd
import pytest

from hydws.parser.parser import (BoreholeHydraulics, SectionHydraulics,
                                 as_uuid, empty_section_metadata,
                                 is_valid_uuid)

DIRPATH = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def df():
    return pd.read_parquet(os.path.join(DIRPATH, 'hydraulics.parquet'))


@pytest.fixture
def hydjson():
    with open(os.path.join(DIRPATH, 'hydraulics.json'), 'rb') as f:
        hydjson = json.load(f)
    return hydjson


@pytest.fixture
def metadata(hydjson):
    metadata = deepcopy(hydjson['sections'][1])
    metadata.pop('hydraulics')
    return metadata


class TestUtilityFunctions:
    def test_is_valid_uuid_valid(self):
        assert is_valid_uuid("29a3a2d8-b5d3-4dd6-bc12-0892874723fc") is True

    def test_as_uuid_with_string(self):
        result = as_uuid("29a3a2d8-b5d3-4dd6-bc12-0892874723fc")
        assert isinstance(result, uuid.UUID)


class TestBoreholeHydraulics:
    def test_init(self, hydjson, df):

        parser = BoreholeHydraulics(hydjson)

        hydjson['sections'][1].pop('hydraulics')
        hydraulics_id = hydjson['sections'][1]['publicid']
        section_json = hydjson.pop('sections')[0]
        section_json.pop('hydraulics')

        assert parser.metadata == hydjson
        pd.testing.assert_frame_equal(parser[hydraulics_id].hydraulics, df)

        assert parser[section_json['publicid']].metadata == section_json
        assert parser.nloc[section_json['name']].metadata == section_json

        for key, value in parser.items():
            assert parser[key] == value

    def test_to_json(self, hydjson):
        parser = BoreholeHydraulics(hydjson)
        borehole_json = parser.to_json()
        assert borehole_json == hydjson

    def test_init_empty(self):
        borehole = BoreholeHydraulics()
        assert borehole.metadata['name'] == 'Unnamed Borehole'
        assert len(borehole) == 0

    def test_query_datetime(self, hydjson):
        borehole = BoreholeHydraulics(hydjson)
        start = datetime(2020, 11, 24, 13, 5, 0)
        end = datetime(2020, 11, 24, 13, 15, 0)
        result = borehole.query_datetime(starttime=start, endtime=end)
        assert isinstance(result, BoreholeHydraulics)

    def test_add_empty_section(self):
        borehole = BoreholeHydraulics()
        section_id = borehole.add_empty_section()
        assert section_id in borehole
        assert len(borehole) == 1

    def test_section_from_json(self, hydjson):
        borehole = BoreholeHydraulics()
        section_id = borehole.section_from_json(hydjson['sections'][1])
        assert borehole[section_id] is not None

    def test_section_from_dataframe(self, df):
        borehole = BoreholeHydraulics()
        section_id = borehole.section_from_dataframe(df)
        assert section_id in borehole

    def test_delitem(self, hydjson):
        borehole = BoreholeHydraulics(hydjson)
        section_id = list(borehole.keys())[0]
        del borehole[section_id]
        assert section_id not in borehole

    def test_len(self, hydjson):
        assert len(BoreholeHydraulics(hydjson)) == 2
        assert len(BoreholeHydraulics()) == 0

    def test_contains(self, hydjson):
        borehole = BoreholeHydraulics(hydjson)
        section_id = list(borehole.keys())[0]
        assert section_id in borehole
        assert uuid.uuid4() not in borehole

    def test_repr(self, hydjson):
        borehole = BoreholeHydraulics(hydjson)
        assert repr(borehole).startswith('<HYDWSParser:')


class TestSectionHydraulics:
    def test_metadata(self):
        hydraulics = SectionHydraulics()
        assert is_valid_uuid(hydraulics.metadata['publicid'])
        del hydraulics.metadata['publicid']
        metadata = empty_section_metadata()
        del metadata['publicid']
        assert hydraulics.metadata == metadata

    def test_load_hydraulic_dataframe(self, df):
        hydraulics = SectionHydraulics()
        hydraulics.hydraulics = df
        pd.testing.assert_frame_equal(hydraulics.hydraulics, df)

    def test_load_hydraulic_json(self, hydjson, df):
        hydraulics = SectionHydraulics()
        hydraulics.load_hydraulic_json(
            hydjson['sections'][1]['hydraulics'])
        pd.testing.assert_frame_equal(hydraulics.hydraulics, df)

    def test_load_section_json(self, hydjson, df, metadata):
        hydraulics = SectionHydraulics()

        hydraulics._from_json(hydjson['sections'][1])
        pd.testing.assert_frame_equal(hydraulics.hydraulics, df)
        assert hydraulics.metadata == metadata

    def test_init(self, hydjson, df, metadata):
        hydraulics = SectionHydraulics(hydjson['sections'][1])
        pd.testing.assert_frame_equal(hydraulics.hydraulics, df)
        assert hydraulics.metadata == metadata

    def test_to_json(self, hydjson, df):
        hydraulics = SectionHydraulics(hydjson['sections'][1])
        hydraulics_json = hydraulics.to_json()
        assert hydraulics_json == hydjson['sections'][1]
        pd.testing.assert_frame_equal(hydraulics.hydraulics, df)

    def test_from_json_without_hydraulics(self, hydjson):
        section_data = deepcopy(hydjson['sections'][0])
        del section_data['hydraulics']
        hydraulics = SectionHydraulics(section_data)
        assert len(hydraulics.hydraulics) == 0

    def test_query_datetime(self, hydjson):
        hydraulics = SectionHydraulics(hydjson['sections'][1])
        start = datetime(2020, 11, 24, 13, 5, 0)
        end = datetime(2020, 11, 24, 13, 15, 0)
        result = hydraulics.query_datetime(starttime=start, endtime=end)
        assert len(result.hydraulics) < len(hydraulics.hydraulics)

    def test_to_json_with_resample(self, hydjson):
        hydraulics = SectionHydraulics(hydjson['sections'][1])
        result = hydraulics.to_json(resample=120)
        assert len(result['hydraulics']) <= len(
            hydjson['sections'][1]['hydraulics'])

    def test_invalid_column_raises(self, df):
        hydraulics = SectionHydraulics()
        invalid_df = df.copy()
        invalid_df['invalid_column'] = 1.0
        with pytest.raises(KeyError):
            hydraulics.hydraulics = invalid_df
