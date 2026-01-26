import json

import pandas as pd
import pytest

from hydws.parser.rawparser import RawHydraulicsParser

# Constants for repeated UUIDs
BOREHOLE_ID = '29a3a2d8-b5d3-4dd6-bc12-0892874723fc'
SECTION_02_ID = 'c0c71ae8-e37a-4ad1-9e91-0407cf0792b1'
SECTION_03_ID = 'f4bfa3dd-d363-4d92-b294-80b69c165ba4'


def make_config_file(config, tmp_path):
    """Helper to create config file from config dict."""
    config_path = tmp_path / 'config.json'
    with open(config_path, 'w') as f:
        json.dump(config, f)
    return str(config_path)


@pytest.fixture
def borehole_metadata():
    """Minimal borehole metadata with two sections."""
    return [{
        'publicid': BOREHOLE_ID,
        'name': 'ST1',
        'altitude': {'value': 1484.905},
        'longitude': {'value': 8.477},
        'latitude': {'value': 46.511},
        'sections': [
            {
                'publicid': SECTION_02_ID,
                'name': 'ST1_section_02',
                'bottomaltitude': {'value': 1204.076},
                'topaltitude': {'value': 1210.150},
                'toplongitude': {'value': 8.474},
                'toplatitude': {'value': 46.509},
                'bottomlongitude': {'value': 8.474},
                'bottomlatitude': {'value': 46.509},
            },
            {
                'publicid': SECTION_03_ID,
                'name': 'ST1_section_03',
                'bottomaltitude': {'value': 1211.367},
                'topaltitude': {'value': 1226.055},
                'toplongitude': {'value': 8.474},
                'toplatitude': {'value': 46.509},
                'bottomlongitude': {'value': 8.474},
                'bottomlatitude': {'value': 46.509},
            }
        ]
    }]


class TestInit:

    def test_builds_maps_and_loads_config(self, borehole_metadata, tmp_path):
        """Verify sections_map, name_map are built and config is loaded."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['p'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02'}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)

        assert 'ST1_section_02' in parser.sections_map
        assert parser.name_map['ST1_section_02'] == SECTION_02_ID
        assert parser.config[0]['fieldName'] == 'toppressure'

    def test_handles_empty_sections(self, tmp_path):
        """Handle borehole metadata without sections key."""
        config_path = make_config_file([], tmp_path)
        metadata = [{'publicid': 'test-id', 'name': 'Test'}]
        parser = RawHydraulicsParser(config_path, metadata)

        assert len(parser.sections_map) == 0


class TestParse:

    def test_output_formats(self, borehole_metadata, tmp_path):
        """Parse returns correct type for json and hydwsparser formats."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['p'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02'}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'p': [100.0]},
                          index=pd.date_range('2020-11-24', periods=1))

        json_result = parser.parse(df, format='json')
        assert isinstance(json_result, list)
        assert 'sections' in json_result[0]

        obj_result = parser.parse(df, format='hydwsparser')
        assert isinstance(obj_result, dict)
        assert BOREHOLE_ID in obj_result

    def test_invalid_format_raises(self, borehole_metadata, tmp_path):
        """Parse raises KeyError for unknown format."""
        config_path = make_config_file([], tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)

        with pytest.raises(KeyError, match='Return format unknown'):
            parser.parse(pd.DataFrame(), format='invalid')

    def test_skips_missing_columns_and_zero_data(self, borehole_metadata,
                                                 tmp_path):
        """Missing columns and all-zero data are skipped gracefully."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['missing'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02'}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)

        # Missing column
        df = pd.DataFrame({'other': [1.0]},
                          index=pd.date_range('2020-11-24', periods=1))
        assert parser.parse(df, format='json') == []

        # Empty dataframe
        assert parser.parse(pd.DataFrame(), format='json') == []

    def test_sums_multiple_columns(self, borehole_metadata, tmp_path):
        """Multiple columnNames are summed when no conditions."""
        config = [{'fieldName': 'topflow', 'columnNames': ['a', 'b'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02'}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'a': [1.0, 2.0], 'b': [0.5, 0.5]},
                          index=pd.date_range('2020-11-24', periods=2))

        result = parser.parse(df, format='hydwsparser')
        hydraulics = result[BOREHOLE_ID][SECTION_02_ID].hydraulics
        assert hydraulics['topflow'].iloc[0] == 1.5
        assert hydraulics['topflow'].iloc[1] == 2.5

    def test_skips_zero_data(self, borehole_metadata, tmp_path):
        """Columns with all zeros are skipped."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['zeros'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02'}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'zeros': [0.0, 0.0]},
                          index=pd.date_range('2020-11-24', periods=2))

        assert parser.parse(df, format='json') == []


class TestConditions:

    @pytest.mark.parametrize('rule,values,expected', [
        pytest.param('above', [40.0, 60.0, 80.0], [
                     0.0, 60.0, 80.0], id='above'),
        pytest.param('below', [40.0, 60.0, 30.0], [
                     40.0, 0.0, 30.0], id='below'),
    ])
    def test_basic_rules(self, borehole_metadata,
                         tmp_path, rule, values, expected):
        """Test above/below condition rules with threshold=50."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['p'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02',
                   'conditions': [{'columnNames': ['p'],
                                   'rule': rule,
                                   'value': 50}]}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'p': values},
                          index=pd.date_range('2020-11-24',
                                              periods=len(values)))

        result = parser.parse(df, format='hydwsparser')
        hydraulics = \
            result[BOREHOLE_ID][SECTION_02_ID].hydraulics['toppressure']
        for i, exp in enumerate(expected):
            assert hydraulics.iloc[i] == exp

    def test_above_current(self, borehole_metadata, tmp_path):
        """'above-current' rule: (condition - current) > value."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['main', 'alt'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02',
                   'conditions': [
                       {'columnNames': ['main'], 'rule': 'above', 'value': 0},
                       {'columnNames': ['alt'],
                           'rule': 'above-current', 'value': 10}
        ]}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'main': [50.0, 50.0, 50.0],
                           'alt': [70.0, 55.0, 100.0]},
                          index=pd.date_range('2020-11-24', periods=3))

        result = parser.parse(df, format='hydwsparser')
        hydraulics = \
            result[BOREHOLE_ID][SECTION_02_ID].hydraulics['toppressure']
        # 70-50=20>10 -> 70; 55-50=5<10 -> 50; 100-50=50>10 -> 100
        assert list(hydraulics) == [70.0, 50.0, 100.0]

    def test_below_current(self, borehole_metadata, tmp_path):
        """'below-current' rule: (current - condition) > value."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['main', 'alt'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02',
                   'conditions': [
                       {'columnNames': ['main'], 'rule': 'above', 'value': 0},
                       {'columnNames': ['alt'],
                           'rule': 'below-current', 'value': 10}
        ]}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'main': [100.0, 50.0, 100.0],
                           'alt': [80.0, 45.0, 50.0]},
                          index=pd.date_range('2020-11-24', periods=3))

        result = parser.parse(df, format='hydwsparser')
        hydraulics = \
            result[BOREHOLE_ID][SECTION_02_ID].hydraulics['toppressure']
        # 100-80=20>10 -> 80; 50-45=5<10 -> 50; 100-50=50>10 -> 50
        assert list(hydraulics) == [80.0, 50.0, 50.0]

    def test_unknown_rule_raises(self, borehole_metadata, tmp_path):
        """Unknown condition rule raises ValueError."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['p'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02',
                   'conditions': [{'columnNames': ['p'],
                                   'rule': 'invalid', 'value': 50}]}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'p': [40.0]},
                          index=pd.date_range('2020-11-24', periods=1))

        with pytest.raises(ValueError):
            parser.parse(df, format='json')

    def test_missing_column_skipped(self, borehole_metadata, tmp_path):
        """Condition with missing column is skipped gracefully."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['p'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02',
                   'conditions': [{'columnNames': ['missing'],
                                   'rule': 'above',
                                   'value': 50}]}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'p': [40.0, 60.0]},
                          index=pd.date_range('2020-11-24', periods=2))

        # Should not raise - returns empty due to all zeros after conditions
        assert parser.parse(df, format='json') == []


class TestUnitConversion:

    @pytest.mark.parametrize('op,factor,input_val,expected', [
        pytest.param('mul', 1000, 1.0, 1000.0, id='multiply'),
        pytest.param('truediv', 10, 100.0, 10.0, id='divide'),
        pytest.param('add', 273.15, 20.0, 293.15, id='add'),
        pytest.param('sub', 50, 100.0, 50.0, id='subtract'),
    ])
    def test_operations(self, borehole_metadata, tmp_path, op, factor,
                        input_val, expected):
        """Test unit conversion operations."""
        config = [{'fieldName': 'topflow', 'columnNames': ['v'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02',
                   'unitConversion': [op, factor]}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'v': [input_val]},
                          index=pd.date_range('2020-11-24', periods=1))

        result = parser.parse(df, format='hydwsparser')
        actual = \
            result[BOREHOLE_ID][SECTION_02_ID].hydraulics['topflow'].iloc[0]
        assert actual == pytest.approx(expected)


class TestSurfacePressureCorrection:

    def test_adds_hydrostatic_head(self, borehole_metadata, tmp_path):
        """Surface pressure adds hydrostatic head for pressure fields."""
        config = [{'fieldName': 'toppressure', 'columnNames': ['p'],
                   'assignTo': 'sectionID', 'section': 'ST1_section_02',
                   'sensorPosition': 'surface'}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'p': [1000000.0]},
                          index=pd.date_range('2020-11-24', periods=1))

        result = parser.parse(df, format='hydwsparser')
        actual = result[BOREHOLE_ID][SECTION_02_ID
                                     ].hydraulics['toppressure'].iloc[0]
        # rho * g * h = 998.2 * 9.81 * (1484.905 - 1204.076)
        correction = 998.2 * (1484.905 - 1204.076) * 9.81
        assert actual == pytest.approx(1000000.0 + correction, rel=1e-3)

    def test_no_correction_for_downhole_or_non_pressure(self,
                                                        borehole_metadata,
                                                        tmp_path):
        """No correction for downhole sensors or non-pressure fields."""
        config = [
            {'fieldName': 'toppressure', 'columnNames': ['dp'],
             'assignTo': 'sectionID', 'section': 'ST1_section_02',
             'sensorPosition': 'downhole'},
            {'fieldName': 'topflow', 'columnNames': ['sf'],
             'assignTo': 'sectionID', 'section': 'ST1_section_02',
             'sensorPosition': 'surface'}
        ]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'dp': [1000000.0], 'sf': [0.001]},
                          index=pd.date_range('2020-11-24', periods=1))

        result = parser.parse(df, format='hydwsparser')
        section = result[BOREHOLE_ID][SECTION_02_ID]
        # no correction
        assert section.hydraulics['toppressure'].iloc[0] == 1000000.0
        assert section.hydraulics['topflow'].iloc[0] == 0.001  # no correction


class TestPlanAssignment:

    def test_routes_by_time_period(self, borehole_metadata, tmp_path):
        """Plan assigns data to sections based on time periods."""
        plan_path = tmp_path / 'plan.csv'
        plan_path.write_text("""date_from, date_until, interval
2020/11/24T13:00:00, 2020/11/24T13:03:00, ST1_section_02
2020/11/24T13:03:00, 2020/11/24T13:06:00, ST1_section_03""")

        config = [{'fieldName': 'toppressure', 'columnNames': ['p'],
                   'assignTo': 'plan', 'section': str(plan_path)}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'p': range(6)},
                          index=pd.date_range('2020-11-24 13:00',
                                              periods=6, freq='1min'))

        result = parser.parse(df, format='hydwsparser')
        borehole = result[BOREHOLE_ID]
        assert len(borehole[SECTION_02_ID].hydraulics) > 0
        assert len(borehole[SECTION_03_ID].hydraulics) > 0

    def test_empty_period_skipped(self, borehole_metadata, tmp_path):
        """Plan periods with no data are skipped."""
        plan_path = tmp_path / 'plan.csv'
        plan_path.write_text("""date_from, date_until, interval
2020/11/24T13:00:00, 2020/11/24T13:05:00, ST1_section_02
2020/11/24T14:00:00, 2020/11/24T14:05:00, ST1_section_03""")

        config = [{'fieldName': 'toppressure', 'columnNames': ['p'],
                   'assignTo': 'plan', 'section': str(plan_path)}]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        # Data only for first period
        df = pd.DataFrame({'p': [1.0, 2.0, 3.0]},
                          index=pd.date_range('2020-11-24 13:00',
                                              periods=3, freq='1min'))

        result = parser.parse(df, format='hydwsparser')
        borehole = result[BOREHOLE_ID]
        assert len(borehole[SECTION_02_ID].hydraulics) > 0
        assert borehole[SECTION_03_ID].hydraulics is None or \
            len(borehole[SECTION_03_ID].hydraulics) == 0


class TestMultipleFields:

    def test_concatenates_to_same_section(self, borehole_metadata, tmp_path):
        """Multiple config entries add different fields to same section."""
        config = [
            {'fieldName': 'toppressure', 'columnNames': ['p'],
             'assignTo': 'sectionID', 'section': 'ST1_section_02'},
            {'fieldName': 'topflow', 'columnNames': ['f'],
             'assignTo': 'sectionID', 'section': 'ST1_section_02'}
        ]
        config_path = make_config_file(config, tmp_path)
        parser = RawHydraulicsParser(config_path, borehole_metadata)
        df = pd.DataFrame({'p': [100.0, 200.0], 'f': [0.001, 0.002]},
                          index=pd.date_range('2020-11-24', periods=2))

        result = parser.parse(df, format='hydwsparser')
        section = result[BOREHOLE_ID][SECTION_02_ID]
        assert 'toppressure' in section.hydraulics.columns
        assert 'topflow' in section.hydraulics.columns
        assert len(section.hydraulics) == 2
