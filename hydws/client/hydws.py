import io
import json
import logging
import uuid
from datetime import datetime

import pandas as pd
import requests

from hydws import ClientError, NoContent, RequestsError, make_request
from hydws.parser.schema import BoreholeSchema


class HYDWSDataSource:
    """
    Fetching data from *HYDWS*.
    """

    def __init__(self,
                 url: str,
                 timeout: int = None,
                 api_key: str = None,
                 starttime: datetime = None,
                 endtime: datetime = None,
                 minlatitude: float = None,
                 maxlatitude: float = None,
                 minlongitude: float = None,
                 maxlongitude: float = None) -> None:
        """
        Initialize Class.
        :param url:          URL of the hydrological webservice
        :param timeout:      after how long, contacting the webservice should
                             be aborted
        :param api_key:      API key for write operations (POST/DELETE)
        :param starttime:    Filter boreholes with data after this time
        :param endtime:      Filter boreholes with data before this time
        :param minlatitude:  Filter boreholes with latitude >= this value
        :param maxlatitude:  Filter boreholes with latitude <= this value
        :param minlongitude: Filter boreholes with longitude >= this value
        :param maxlongitude: Filter boreholes with longitude <= this value
        """
        self.url = url
        self._timeout = timeout
        self._api_key = api_key
        self.logger = logging.getLogger(__name__)

        params = {}
        if starttime is not None:
            params['starttime'] = starttime.strftime("%Y-%m-%dT%H:%M:%S")
        if endtime is not None:
            params['endtime'] = endtime.strftime("%Y-%m-%dT%H:%M:%S")
        if minlatitude is not None:
            params['minlatitude'] = minlatitude
        if maxlatitude is not None:
            params['maxlatitude'] = maxlatitude
        if minlongitude is not None:
            params['minlongitude'] = minlongitude
        if maxlongitude is not None:
            params['maxlongitude'] = maxlongitude

        self.metadata = self._make_api_request(
            f'{self.url}/boreholes', params)

    def list_boreholes(self) -> list:
        """
        Returns a list of all boreholes including their metadata and sections.
        """
        return self.metadata

    def list_borehole_names(self, identifier: str = 'name') \
            -> list[tuple[str, str]] | list[str]:
        """
        Returns a list of all borehole names and id's.
        :param identifier: 'name', 'publicid' or 'both'.

        :returns: List of tuples with borehole name and id.
        """
        if identifier == 'both':
            return [(bh['name'], bh['publicid']) for bh in self.metadata]
        else:
            return [bh[identifier] for bh in self.metadata]

    def get_borehole_metadata(self, borehole: str) -> dict:
        """
        Returns borehole and section metadata as a dict.

        :param borehole: PublicID or name of the borehole.
        :returns:        Borehole data as a dict.
        """

        try:
            uuid.UUID(borehole)
            key = 'publicid'
        except ValueError:
            key = 'name'

        borehole_metadata = next(
            (bh for bh in self.metadata if bh[key] == borehole), None)

        if not borehole_metadata:
            raise KeyError(f'Borehole {borehole} could not be found.')

        return borehole_metadata

    def list_sections(self, borehole: str) -> list:
        """
        Returns a list of all sections for a given borehole.

        :param borehole: PublicID or name of the borehole.

        :returns:        List of sections for the borehole.
        """

        borehole_metadata = self.get_borehole_metadata(borehole)

        return borehole_metadata['sections']

    def list_section_names(self, borehole: str, identifier: str = 'name') \
            -> list[tuple[str, str] | list[str]]:
        """
        Returns a list of all section names and id's for a given borehole.

        :param borehole:   PublicID or name of the borehole.
        :param identifier: 'name', 'publicid' or 'both'.
        :returns:          List of tuples with section name and id.
        """

        borehole_metadata = self.get_borehole_metadata(borehole)

        if identifier == 'both':
            return [(sc['name'], sc['publicid'])
                    for sc in borehole_metadata['sections']]
        else:
            return [sc[identifier] for sc in borehole_metadata['sections']]

    def get_section_metadata(self, borehole: str, section: str) -> dict:
        """
        Returns metadata for a given section.

        :param borehole: PublicID or name of the borehole.
        :param section:  PublicID or name of the section.
        :returns:        Metadata for the section.
        """

        borehole_metadata = self.get_borehole_metadata(borehole)

        try:
            uuid.UUID(section)
            key = 'publicid'
        except ValueError:
            key = 'name'

        section_metadata = next(
            (sc for sc in borehole_metadata['sections']
             if sc[key] == section), None)

        if not section_metadata:
            raise KeyError(f'Section {section} could not be found.')

        return section_metadata

    def get_borehole(self, borehole: str,
                     starttime: datetime = datetime(1990, 1, 1),
                     endtime: datetime = datetime.now()) -> dict:
        """
        Returns borehole with all the sections and associated hydraulic data.

        :param borehole:  PublicID or name of the borehole.
        :param starttime: Datetime from when on the data should be retrieved.
        :param endtime:   Datetime until when the data should be retrieved.

        :returns: Borehole and section metadata as well as section hydraulics.
        """
        borehole_id = self._get_borehole_id(borehole)

        request_url = f'{self.url}/boreholes/{borehole_id}'

        params = {
            'starttime': starttime.strftime("%Y-%m-%dT%H:%M:%S"),
            'endtime': endtime.strftime("%Y-%m-%dT%H:%M:%S"),
            'level': 'hydraulic'}

        metadata = self._make_api_request(request_url, params)

        return metadata

    def get_section(self, borehole: str,
                    section: str,
                    starttime: datetime,
                    endtime: datetime = datetime.now()) -> dict:
        """
        Returns Section data including hydraulics.

        :param borehole:  PublicID or name of the borehole.
        :param section:   PublicID or name of the section.
        :param starttime: Datetime from when on the data should be retrieved.
        :param endtime:   Datetime until when the data should be retrieved.

        :returns: Section metadata as well as section hydraulics.
        """
        borehole_id = self._get_borehole_id(borehole)
        section_id = self._get_section_id(borehole_id, section)

        section_metadata = self.get_section_metadata(borehole_id, section_id)
        section_hydraulics = self.get_section_hydraulics(
            borehole_id, section_id, starttime, endtime)

        section_metadata['hydraulics'] = section_hydraulics
        return section_metadata

    def get_section_hydraulics(
            self, borehole: str,
            section: str,
            starttime: datetime,
            endtime: datetime = datetime.now(),
            format: str = 'json') -> list | pd.DataFrame:
        """
        Get section hydraulics without any metadata.

        :param borehole:    PublicID or name of the borehole.
        :param section:     PublicID or name of the section.
        :param starttime:   Datetime from when on the data should be retrieved.
        :param endtime:     Datetime until when the data should be retrieved.
        :param format:      Format of the returned data: 'json' or 'pandas'.

        :returns: List of hydraulic samples (json) or DataFrame (pandas).
        """
        borehole_id = self._get_borehole_id(borehole)
        section_id = self._get_section_id(borehole_id, section)

        params = {
            'starttime': starttime.strftime("%Y-%m-%dT%H:%M:%S"),
            'endtime': endtime.strftime("%Y-%m-%dT%H:%M:%S")}

        if format == 'pandas':
            params['format'] = 'csv'

        self.logger.info(
            f"Request borehole / hydraulic data from hydws (url={self.url}, "
            f"borehole={borehole_id}, section={section_id}, params={params}).")

        request_url = \
            f'{self.url}/boreholes/{borehole_id}/' \
            f'sections/{section_id}/hydraulics'

        if format == 'pandas':
            csv_data = self._make_api_request(
                request_url, params, parse_json=False)
            if not csv_data:
                return pd.DataFrame()
            df = pd.read_csv(
                io.StringIO(csv_data), parse_dates=['datetime_value'])
            # Strip _value suffix from columns to match JSON format
            df.columns = df.columns.str.replace('_value', '', regex=False)
            df.set_index('datetime', inplace=True)
            return df

        hydraulics = self._make_api_request(request_url, params)

        if not hydraulics:
            return []

        return hydraulics

    def post_borehole(self, borehole, merge: bool = False,
                      merge_limit: int = 60, test: bool = False) -> dict:
        """
        Post borehole data to the API.

        :param borehole:    BoreholeHydraulics object or dict
        :param merge:       Merge with existing data if True
        :param merge_limit: Time limit for merging (seconds)
        :param test:        If True, validate and print stats without posting

        :returns: Created borehole data from API (or None in test mode)
        """
        data = borehole.to_json() if hasattr(borehole, 'to_json') else borehole

        if test:
            BoreholeSchema.model_validate(data)
            name = data.get('name', 'Unnamed')
            sections = data.get('sections', [])
            n_sections = len(sections)
            hydraulics_counts = [
                len(s.get('hydraulics', [])) for s in sections
            ]
            total_hydraulics = sum(hydraulics_counts)
            print(f"Borehole: {name}")
            print(f"Sections: {n_sections}")
            print(f"Total hydraulics: {total_hydraulics}")
            for s in sections:
                s_name = s.get('name', 'Unnamed')
                s_hydraulics = len(s.get('hydraulics', []))
                print(f"  - {s_name}: {s_hydraulics} hydraulic samples")
            return None

        params = {'merge': str(merge).lower(), 'merge_limit': merge_limit}
        headers = {'x-api-key': self._api_key} if self._api_key else {}

        try:
            response = make_request(requests.post,
                                    f'{self.url}/boreholes',
                                    params,
                                    self._timeout,
                                    nocontent_codes=(),
                                    success_codes=(200, 201),
                                    headers=headers,
                                    json=data)
            return json.loads(response)
        except ClientError as err:
            if err.response.status_code == 401 and not self._api_key:
                raise ClientError(
                    "Authentication failed (401). "
                    "Consider providing api_key parameter.",
                    response=err.response)
            raise

    def delete_borehole(self, borehole: str, test: bool = False) -> None:
        """
        Delete a borehole.

        :param borehole: PublicID or name of the borehole
        :param test:     If True, check existence and print info
        """
        borehole_id = self._get_borehole_id(borehole)

        if test:
            request_url = f'{self.url}/boreholes/{borehole_id}'
            response = make_request(requests.get,
                                    request_url,
                                    {},
                                    self._timeout,
                                    nocontent_codes=(404,),
                                    success_codes=(200,))
            borehole_data = json.loads(response)
            name = borehole_data.get('name', 'Unnamed')
            sections = borehole_data.get('sections', [])
            print(f"Borehole: {name}")
            print(f"Sections: {len(sections)}")
            print("Would be deleted.")
            return

        headers = {'x-api-key': self._api_key} if self._api_key else {}

        try:
            make_request(requests.delete,
                         f'{self.url}/boreholes/{borehole_id}',
                         {},
                         self._timeout,
                         nocontent_codes=(),
                         success_codes=(200, 204),
                         headers=headers)
        except ClientError as err:
            if err.response.status_code == 401 and not self._api_key:
                raise ClientError(
                    "Authentication failed (401). "
                    "Consider providing api_key parameter.",
                    response=err.response)
            raise

    def delete_section(self, borehole: str, section: str,
                       test: bool = False) -> None:
        """
        Delete a section and its hydraulic data.

        :param borehole: PublicID or name of the borehole
        :param section:  PublicID or name of the section
        :param test:     If True, check existence and print info
        """
        borehole_id = self._get_borehole_id(borehole)
        section_id = self._get_section_id(borehole_id, section)

        url = f'{self.url}/boreholes/{borehole_id}/sections/{section_id}'

        if test:
            response = make_request(requests.get,
                                    url,
                                    {},
                                    self._timeout,
                                    nocontent_codes=(404,),
                                    success_codes=(200,))
            section_data = json.loads(response)
            name = section_data.get('name', 'Unnamed')
            hydraulics = section_data.get('hydraulics', [])
            print(f"Section: {name}")
            print(f"Hydraulic samples: {len(hydraulics)}")
            print("Would be deleted.")
            return

        headers = {'x-api-key': self._api_key} if self._api_key else {}

        try:
            make_request(requests.delete,
                         url,
                         {},
                         self._timeout,
                         nocontent_codes=(),
                         success_codes=(200, 204),
                         headers=headers)
        except ClientError as err:
            if err.response.status_code == 401 and not self._api_key:
                raise ClientError(
                    "Authentication failed (401). "
                    "Consider providing api_key parameter.",
                    response=err.response)
            raise

    def delete_section_hydraulics(self, borehole: str, section: str,
                                  starttime: datetime = None,
                                  endtime: datetime = None,
                                  test: bool = False) -> None:
        """
        Delete hydraulic samples for a section.

        :param borehole:  PublicID or name of the borehole
        :param section:   PublicID or name of the section
        :param starttime: Optional start of time range to delete
        :param endtime:   Optional end of time range to delete
        :param test:      If True, show count without deleting
        """
        borehole_id = self._get_borehole_id(borehole)
        section_id = self._get_section_id(borehole_id, section)

        params = {}
        if starttime:
            params['starttime'] = starttime.strftime("%Y-%m-%dT%H:%M:%S")
        if endtime:
            params['endtime'] = endtime.strftime("%Y-%m-%dT%H:%M:%S")

        url = f'{self.url}/boreholes/{borehole_id}/sections/{section_id}' \
            f'/hydraulics'

        if test:
            response = make_request(requests.get,
                                    url,
                                    params,
                                    self._timeout,
                                    nocontent_codes=(204, 404),
                                    success_codes=(200,))
            hydraulics = json.loads(response)
            count = len(hydraulics) if hydraulics else 0
            print(f"Hydraulic samples to delete: {count}")
            return

        headers = {'x-api-key': self._api_key} if self._api_key else {}

        try:
            make_request(
                requests.delete,
                url,
                params,
                self._timeout,
                nocontent_codes=(),
                success_codes=(200, 204),
                headers=headers)
        except ClientError as err:
            if err.response.status_code == 401 and not self._api_key:
                raise ClientError(
                    "Authentication failed (401). "
                    "Consider providing api_key parameter.",
                    response=err.response)
            raise

    def _get_borehole_id(self, borehole_name: str) -> str:
        """
        Get the borehole ID by its name.
        """
        # check whether it is a valid UUID
        try:
            uuid.UUID(borehole_name)
            return borehole_name
        except ValueError:
            pass

        # if not, get the borehole ID by its name
        borehole = next(
            (bh for bh in self.metadata if bh['name'] == borehole_name), None)

        if not borehole:
            raise KeyError(f'Borehole {borehole_name} could not be found.')

        return borehole['publicid']

    def _get_section_id(self, borehole_id: str, section_name: str) -> str:
        """
        Get the section ID by its name.
        """
        # check whether it is a valid UUID
        try:
            uuid.UUID(section_name)
            return section_name
        except ValueError:
            pass

        # if not, get the section ID by its name
        borehole_metadata = self.get_borehole_metadata(borehole_id)
        section = next(
            (section for section in borehole_metadata['sections']
             if section['name'] == section_name), None)

        if not section:
            raise KeyError(f'Section {section_name} could not be found.')

        return section['publicid']

    def _make_api_request(self, request_url: str, params: dict = {},
                          parse_json: bool = True):
        try:
            response = make_request(
                requests.get,
                request_url,
                params,
                self._timeout,
                nocontent_codes=(
                    204,
                    404))

        except NoContent:
            return {} if parse_json else ''
        except RequestsError as err:
            self.logger.error(f"Request Error while fetching data ({err}).")
            raise
        else:
            self.logger.info('HYDWS data received.')
            if parse_json:
                return json.loads(response)
            return response.decode('utf-8')
