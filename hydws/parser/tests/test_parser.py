import json
import os
from copy import deepcopy

import pandas as pd

from hydws.parser.parser import HYDJSONParser

DIRPATH = os.path.dirname(os.path.abspath(__file__))


def test_parser():
    parser = HYDJSONParser()

    with open(os.path.join(DIRPATH, 'hydraulics.json'), 'rb') as f:
        data = json.load(f)

    parser.load_borehole_json(data)
    df = parser.get_hydraulics_dataframe_by_name('ST1_section_02')

    df2 = pd.read_parquet(os.path.join(DIRPATH, 'hydraulics.parquet'))

    pd.testing.assert_frame_equal(df, df2)


def test_new_parser():
    parser = HYDJSONParser()
    test_df = pd.read_parquet(os.path.join(DIRPATH, 'hydraulics.parquet'))

    with open(os.path.join(DIRPATH, 'hydraulics.json'), 'rb') as f:
        data = json.load(f)

    parser.load_borehole_json(data)

    borehole_metadata = deepcopy(data)
    borehole_metadata['sections'][1].pop('hydraulics')
    section_metadata = deepcopy(data['sections'][1])
    section_metadata.pop('hydraulics')

    borehole_id = borehole_metadata['publicid']
    section_id = section_metadata['publicid']
    section_df = parser.hydraulics[section_id]

    # test metadata and hydraulics access
    pd.testing.assert_frame_equal(section_df, test_df)
    assert section_metadata == parser.metadata[section_id]
    assert borehole_metadata == parser.metadata[borehole_id]


def test_general():

    mydict = {'a': [1, 2, 3]}
    mydict['b'] = mydict['a']

    mydict['a'].append(4)
    print(mydict)
