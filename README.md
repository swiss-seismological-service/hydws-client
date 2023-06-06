# HYDWS Client
_Hydraulic Web Service Client_

This client can be used to access the data from a Hydraulic Webservice more comfortably.

## Installation
Currently the package still needs to be installed via the github repository:

```bash
pip install git+https://gitlab.seismo.ethz.ch/indu/hydws-client.git
```

## Usage

Specifying the URL of the webservice and creating an client object.
```python
from hydws.client import HYDWSDataSource
hydws_url = 'http://bedretto-hydws.ethz.ch:8080/hydws/v1'
hydws = HYDWSDataSource(hydws_url)
```

This can be used to explore the data available from the webservice.
```python
boreholes_metadata = hydws.list_boreholes()
pprint(boreholes_metadata)
```

```json
[{"altitude": {"value": 1484.905},
  "bedrockaltitude": {},
  "institution": "BedrettoLab",
  "latitude": {"value": 46.51113250987997},
  "location": "Bedretto",
  "longitude": {"value": 8.47706629603003},
  "measureddepth": {"value": 400.0},
  "name": "ST1",
  "publicid": "29a3a2d8-b5d3-4dd6-bc12-0892874723fc",
  "sections": [{"bottomaltitude": {"value": 1204.076431828354},
                "bottomclosed": True,
                "bottomlatitude": {"value": 46.50964538043515},
                "bottomlongitude": {"value": 8.47468833805559},
                "bottommeasureddepth": {"value": 373.92},
                "casingdiameter": {"value": 0.0893},
                "endtime": "2023-04-21T23:59:59",
                "holediameter": {"value": 0.216},
                "hydraulics": [],
                "name": "ST1_section_02",
                "publicid": "c0c71ae8-e37a-4ad1-9e91-0407cf0792b1",
                "starttime": "2021-11-16T00:00:59",
                "topaltitude": {"value": 1210.1501322748682},
                "topclosed": True,
                "toplatitude": {"value": 46.50967234897535},
                "toplongitude": {"value": 8.47473203423232},
                "topmeasureddepth": {"value": 366.39}}]}]
```

Hydraulic Data can be retrieved on a borehole section level, filtered by time:
```python
# specify time range of interest
hydraulics_start = datetime(2022, 1, 26)
hydraulics_end = datetime(2022, 1, 27)

# choose borehole and section of interest
borehole_name = 'ST1'
borehole_publicid = '29a3a2d8-b5d3-4dd6-bc12-0892874723fc'
section_name = 'ST1_section_12'
section_publicid = '350706fb-231d-41e8-b9fd-5aa006446df6'

# make the request
well_hydraulics = hydws.get_section(
    borehole_publicid,
    section_publicid,
    hydraulics_start,
    hydraulics_end)

# or make the request using the names
well_hydraulics = hydws.get_section_by_name(
    borehole_name,
    section_name,
    hydraulics_start,
    hydraulics_end)
```

Those hydraulics are now available as dictionaries. To convert them to Pandas DataFrames, the `HYDWSParser` can be used:

```python
from hydws.parser import HYDWSParser
parser = HYDWSParser()
parser.load_borehole_json(well_hydraulics)
```

The data can now be accessed using the following methods:

```python
# converted to a dataframe
sec12_df = parser.get_hydraulics_dataframe(section_publicid)
# or
sec12_df = parser.get_hydraulics_dataframe_by_name(section_name)

print(sec12_df)
```

```
                             toppressure  toptemperature
datetime                                                
1970-01-01 00:27:23.155211  3.506850e+06         293.840
1970-01-01 00:27:23.155271  3.506812e+06         293.840
1970-01-01 00:27:23.155331  3.506801e+06         293.840
1970-01-01 00:27:23.155391  3.506816e+06         293.840
1970-01-01 00:27:23.155451  3.506809e+06         293.840
...                                  ...             ...
1970-01-01 00:27:23.241359  3.506636e+06         293.480
1970-01-01 00:27:23.241419  3.506628e+06         293.480
1970-01-01 00:27:23.241479  3.506671e+06         293.480
1970-01-01 00:27:23.241539  3.506634e+06         293.480
1970-01-01 00:27:23.241599  3.506621e+06         293.483
```

And new data can be read into the parser accordingly:
```python
# load it back into the parser
parser.load_hydraulics_dataframe(section_publicid, sec12_df)
# or
parser.load_hydraulics_dataframe_by_name(section_name, sec12_df)
```

