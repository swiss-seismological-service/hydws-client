"""Tests for HYDWSDataSource client."""
import json
import os
from copy import deepcopy
from datetime import datetime

import pandas as pd
import pytest
import responses

from hydws.client import HYDWSDataSource

BASE_URL = "http://test.example.com/hydws/v1"
DIRPATH = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def borehole_json():
    with open(os.path.join(DIRPATH, 'hydraulics.json')) as f:
        return json.load(f)


@pytest.fixture
def metadata_json(borehole_json):
    """API /boreholes returns list without hydraulics."""
    data = deepcopy(borehole_json)
    for section in data['sections']:
        section.pop('hydraulics', None)
    return [data]


@pytest.fixture
def hydraulics_json(borehole_json):
    return borehole_json['sections'][1]['hydraulics']


class TestBoreholeOperations:
    @responses.activate
    def test_init_and_list_boreholes(self, metadata_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        client = HYDWSDataSource(BASE_URL)
        assert client.list_boreholes() == metadata_json

    @responses.activate
    def test_list_borehole_names(self, metadata_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        client = HYDWSDataSource(BASE_URL)
        assert client.list_borehole_names() == ["ST1"]
        assert client.list_borehole_names('publicid')[0] == \
            metadata_json[0]['publicid']
        assert client.list_borehole_names('both') == \
            [("ST1", metadata_json[0]['publicid'])]

    @responses.activate
    def test_get_borehole_metadata_by_name_and_uuid(self, metadata_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        client = HYDWSDataSource(BASE_URL)
        assert client.get_borehole_metadata("ST1")['name'] == "ST1"
        assert client.get_borehole_metadata(
            metadata_json[0]['publicid'])['name'] == "ST1"

    @responses.activate
    def test_get_borehole_metadata_not_found(self, metadata_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        client = HYDWSDataSource(BASE_URL)
        with pytest.raises(KeyError):
            client.get_borehole_metadata("nonexistent")


class TestSectionOperations:
    @responses.activate
    def test_list_sections(self, metadata_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        client = HYDWSDataSource(BASE_URL)
        assert len(client.list_sections("ST1")) == 2

    @responses.activate
    def test_list_section_names(self, metadata_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        client = HYDWSDataSource(BASE_URL)
        names = client.list_section_names("ST1")
        assert "ST1_section_02" in names
        ids = client.list_section_names("ST1", 'publicid')
        assert len(ids) == 2
        both = client.list_section_names("ST1", 'both')
        assert len(both) == 2
        assert both[1][0] == "ST1_section_02"

    @responses.activate
    def test_get_section_metadata(self, metadata_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        client = HYDWSDataSource(BASE_URL)
        section = client.get_section_metadata("ST1", "ST1_section_02")
        assert section['name'] == "ST1_section_02"

    @responses.activate
    def test_get_section_metadata_not_found(self, metadata_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        client = HYDWSDataSource(BASE_URL)
        with pytest.raises(KeyError):
            client.get_section_metadata("ST1", "nonexistent")


class TestHydraulicData:
    @responses.activate
    def test_get_borehole(self, metadata_json, borehole_json):
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        responses.add(
            responses.GET,
            f"{BASE_URL}/boreholes/{borehole_json['publicid']}",
            json=borehole_json)
        client = HYDWSDataSource(BASE_URL)
        result = client.get_borehole(
            "ST1", datetime(2020, 11, 1), datetime(2020, 12, 1))
        assert result['name'] == "ST1"
        assert "level=hydraulic" in responses.calls[1].request.url

    @responses.activate
    def test_get_section(self, metadata_json, hydraulics_json):
        section_id = "c0c71ae8-e37a-4ad1-9e91-0407cf0792b1"
        borehole_id = metadata_json[0]['publicid']
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        responses.add(
            responses.GET,
            f"{BASE_URL}/boreholes/{borehole_id}/sections/{section_id}"
            "/hydraulics",
            json=hydraulics_json)
        client = HYDWSDataSource(BASE_URL)
        result = client.get_section(
            "ST1", "ST1_section_02",
            datetime(2020, 11, 1), datetime(2020, 12, 1))
        assert result['name'] == "ST1_section_02"
        assert 'hydraulics' in result

    @responses.activate
    def test_get_section_hydraulics_json(self, metadata_json, hydraulics_json):
        section_id = "c0c71ae8-e37a-4ad1-9e91-0407cf0792b1"
        borehole_id = metadata_json[0]['publicid']
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        responses.add(
            responses.GET,
            f"{BASE_URL}/boreholes/{borehole_id}/sections/{section_id}"
            "/hydraulics",
            json=hydraulics_json)
        client = HYDWSDataSource(BASE_URL)
        result = client.get_section_hydraulics(
            "ST1", "ST1_section_02",
            datetime(2020, 11, 1), datetime(2020, 12, 1))
        assert isinstance(result, list)
        assert len(result) == 29

    @responses.activate
    def test_get_section_hydraulics_pandas(self,
                                           metadata_json,
                                           hydraulics_json):
        section_id = "c0c71ae8-e37a-4ad1-9e91-0407cf0792b1"
        borehole_id = metadata_json[0]['publicid']
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        responses.add(
            responses.GET,
            f"{BASE_URL}/boreholes/{borehole_id}/sections/{section_id}"
            "/hydraulics",
            json=hydraulics_json)
        client = HYDWSDataSource(BASE_URL)
        result = client.get_section_hydraulics(
            "ST1", "ST1_section_02",
            datetime(2020, 11, 1), datetime(2020, 12, 1),
            format='pandas')
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 29

    @responses.activate
    def test_get_section_hydraulics_empty(self, metadata_json):
        section_id = "f4bfa3dd-d363-4d92-b294-80b69c165ba4"
        borehole_id = metadata_json[0]['publicid']
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        responses.add(
            responses.GET,
            f"{BASE_URL}/boreholes/{borehole_id}/sections/{section_id}"
            "/hydraulics",
            status=204)
        client = HYDWSDataSource(BASE_URL)
        result = client.get_section_hydraulics(
            "ST1", "ST1_section_03",
            datetime(2020, 11, 1), datetime(2020, 12, 1))
        assert result == []

    @responses.activate
    def test_get_section_hydraulics_empty_pandas(self, metadata_json):
        section_id = "f4bfa3dd-d363-4d92-b294-80b69c165ba4"
        borehole_id = metadata_json[0]['publicid']
        responses.add(
            responses.GET, f"{BASE_URL}/boreholes", json=metadata_json)
        responses.add(
            responses.GET,
            f"{BASE_URL}/boreholes/{borehole_id}/sections/{section_id}"
            "/hydraulics",
            status=204)
        client = HYDWSDataSource(BASE_URL)
        result = client.get_section_hydraulics(
            "ST1", "ST1_section_03",
            datetime(2020, 11, 1), datetime(2020, 12, 1),
            format='pandas')
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
