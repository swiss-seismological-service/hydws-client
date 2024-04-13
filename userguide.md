# HYDWS Client
Hydraulic Web Service Client
This client can be used to access the data from a Hydraulic Webservice more comfortably.

## Installation
Currently the package needs to be installed via the github repository:
```bash
pip install git+https://gitlab.seismo.ethz.ch/indu/hydws-client.git
```

## Usage

### Imports


```python
from datetime import datetime

from hydws.client import HYDWSDataSource
from hydws.parser import BoreholeHydraulics, SectionHydraulics
```

### TLDR; How to get the data?


```python
hydws_url = 'http://scforge.ethz.ch:8081/hydws/v1'
hydws = HYDWSDataSource(hydws_url)
```

Assuming you know exactly what you want, you can use the following methods to get the data you need. Throughout, you can usually use the name and the id interchangeably. Let's assume we have the borehole id, and the section name.


```python
borehole_id = 'caf65646-8093-4aaf-989c-1c837f497667'
section_name = '16A-32/section_03'
hydraulics_start = datetime(2024, 4, 6, 1, 0, 0)
hydraulics_end = datetime(2024, 4, 6, 1, 1, 0)
```

The fastest way to get to the data, without caring about any metadata:


```python
hydraulics = hydws.get_section_hydraulics(borehole_id, section_name, hydraulics_start, hydraulics_end, format='pandas')
hydraulics
```




<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>topflow</th>
      <th>toppressure</th>
    </tr>
    <tr>
      <th>datetime</th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2024-04-06 01:00:00</th>
      <td>0.212990</td>
      <td>4.710498e+07</td>
    </tr>
    <tr>
      <th>2024-04-06 01:00:01</th>
      <td>0.212990</td>
      <td>4.719461e+07</td>
    </tr>
    <tr>
      <th>2024-04-06 01:00:02</th>
      <td>0.212990</td>
      <td>4.721530e+07</td>
    </tr>
    <tr>
      <th>2024-04-06 01:00:03</th>
      <td>0.212831</td>
      <td>4.716703e+07</td>
    </tr>
    <tr>
      <th>2024-04-06 01:00:04</th>
      <td>0.212646</td>
      <td>4.714635e+07</td>
    </tr>
    <tr>
      <th>...</th>
      <td>...</td>
      <td>...</td>
    </tr>
    <tr>
      <th>2024-04-06 01:00:56</th>
      <td>0.213653</td>
      <td>4.716703e+07</td>
    </tr>
    <tr>
      <th>2024-04-06 01:00:57</th>
      <td>0.213308</td>
      <td>4.717393e+07</td>
    </tr>
    <tr>
      <th>2024-04-06 01:00:58</th>
      <td>0.213308</td>
      <td>4.710498e+07</td>
    </tr>
    <tr>
      <th>2024-04-06 01:00:59</th>
      <td>0.213308</td>
      <td>4.714635e+07</td>
    </tr>
    <tr>
      <th>2024-04-06 01:01:00</th>
      <td>0.213494</td>
      <td>4.716014e+07</td>
    </tr>
  </tbody>
</table>
<p>61 rows × 2 columns</p>
</div>



Otherwise, if you want the metadata, or need to parse a file containing `hydws`, or prefer an object with the borehole and/or section structure, you can use the hydws client together with `BoreholeHydraulics` and `SectionHydraulics` classes:

If you just want to consider one Section, it's easiest to directly use the `SectionHydraulics` class:



```python
section_json = hydws.get_section(borehole_id, section_name, hydraulics_start, hydraulics_end)
section = SectionHydraulics(section_json)

section.metadata # to access the metadata of the section
section.hydraulics # to access the hydraulic data as a dataframe
```




    {'publicid': '37801a57-90b9-4fb5-83d7-506ee9166acf',
     'starttime': '2022-04-21T11:48:22',
     'endtime': '2024-04-07T05:59:59',
     'topclosed': True,
     'bottomclosed': True,
     'description': '20 ft perforated interval',
     'name': '16A-32/section_03',
     'casingdiameter': {},
     'holediameter': {},
     'bottommeasureddepth': {'value': 3090.67},
     'topmeasureddepth': {'value': 3084.58},
     'bottomaltitude': {'value': -859.4871565276828},
     'bottomlatitude': {'value': 38.504834},
     'bottomlongitude': {'value': -112.895391},
     'topaltitude': {'value': -856.9050717703348},
     'toplatitude': {'value': 38.50489937662338},
     'toplongitude': {'value': -112.8956963417635}}




```python
# Get Borehole, containing all of its sections and their hydraulic data for the given time range
borehole_json = hydws.get_borehole(borehole_id, hydraulics_start, hydraulics_end)
borehole = BoreholeHydraulics(borehole_json)
```

### Navigating Boreholes, Sections and Metadata

If you don't exactly know which names or publicids there are, you can use the following methods to display the available boreholes and sections.


```python
borehole_metadata_all = hydws.list_boreholes() # returns all metadata
borehole_names = hydws.list_borehole_names() # only returns name and publicid
borehole_names
```




    [('16A-32', 'caf65646-8093-4aaf-989c-1c837f497667'),
     ('16B-32', '24eba485-f6e2-41db-a386-50c985deb38b')]



The first column is the name of the borehole, the second one its public ID. It's generally possible to use either of the two for all of the following functions. The same applies to the section names and their IDs.


```python
section_metadata_all = hydws.list_sections() # returns all metadata
section_names = hydws.list_section_names(borehole_names[0][0]) # only returns name and publicid
section_names
```




    [('16A-32/section_01', '8eb6ce9a-247d-4675-8647-880841bb9531'),
     ('16A-32/section_02', '0c38c3dd-08bd-480d-bcaa-65adbb4563a4'),
     ('16A-32/section_03', '37801a57-90b9-4fb5-83d7-506ee9166acf')]



It is also possible to use the`get_borehole_metadata` or the `get_section_metadata` functions to get the metadata of a specific borehole or section.



```python
borehole_name = borehole_names[0][0]
borehole_id = borehole_names[0][1]
section_name = section_names[2][0]
section_id = section_names[2][1]

borehole_metadata = hydws.get_borehole_metadata(borehole_name)
section_metadata = hydws.get_section_metadata(borehole_name, section_name)
section_metadata
```




    {'publicid': '37801a57-90b9-4fb5-83d7-506ee9166acf',
     'starttime': '2022-04-21T11:48:22',
     'endtime': '2024-04-07T05:59:59',
     'topclosed': True,
     'bottomclosed': True,
     'description': '20 ft perforated interval',
     'name': '16A-32/section_03',
     'hydraulics': [],
     'casingdiameter': {},
     'holediameter': {},
     'bottommeasureddepth': {'value': 3090.67},
     'topmeasureddepth': {'value': 3084.58},
     'bottomaltitude': {'value': -859.4871565276828},
     'bottomlatitude': {'value': 38.504834},
     'bottomlongitude': {'value': -112.895391},
     'topaltitude': {'value': -856.9050717703348},
     'toplatitude': {'value': 38.50489937662338},
     'toplongitude': {'value': -112.8956963417635}}




