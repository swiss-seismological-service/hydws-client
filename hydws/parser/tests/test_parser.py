import json
import os
from copy import deepcopy

import pandas as pd
import pytest

from hydws.parser.parser import (BoreholeHydraulics, SectionHydraulics,
                                 empty_section_metadata, is_valid_uuid)

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
