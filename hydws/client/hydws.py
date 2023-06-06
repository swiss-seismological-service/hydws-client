import base64
import json
import logging
from datetime import datetime

import requests

from hydws import NoContent, RequestsError, make_request


class HYDWSDataSource:
    """
    Fetching data from *HYDWS*.
    """

    def __init__(self,
                 url: str,
                 timeout: int = None) -> None:
        """
        Initialize Class.
        :param url:     URL of the hydrological webservice
        :param timeout: after how long, contacting the webservice should
                        be aborted
        """
        self.url = url
        self._timeout = timeout
        self.logger = logging.getLogger(__name__)

    def list_boreholes(self) -> list:
        """
        Returns a list of all boreholes including their metadata and sections.
        """
        request_url = '{}/boreholes'.format(self.url)
        return self._make_api_request(request_url)

    def get_borehole_metadata(self, borehole_id: str) -> dict:
        """
        Returns borehole and section metadata as a dict.

        :param borehole_id: PublicID of the borehole.
        :returns:           Borehole data as a dict
        """

        request_url = f'{self.url}/boreholes/{borehole_id}'

        metadata = self._make_api_request(request_url)

        return metadata

    def get_borehole(self, borehole_id: str,
                     starttime: datetime = datetime(1990, 1, 1),
                     endtime: datetime = datetime.now()) -> dict:
        """
        NOT WORKING YET

        Returns borehole with all the sections and associated hydraulic data.

        :param borehole_id: PublicID of the borehole.
        :param starttime:   Datetime from when on the data should be retrieved.
        :param endtime:     Datetime until when the data should be retrieved.

        :returns: Borehole and section metadata as well as section hydraulics.
        """
        return NotImplementedError
        request_url = f'{self.url}/boreholes/{borehole_id}'

        params = {
            'starttime': starttime.strftime("%Y-%m-%dT%H:%M:%S"),
            'endtime': endtime.strftime("%Y-%m-%dT%H:%M:%S"),
            'level': 'hydraulic'}

        metadata = self._make_api_request(request_url, params)

        return metadata

    def get_section(self, borehole_id: str,
                    section_id: str,
                    starttime: datetime,
                    endtime: datetime = datetime.now()) -> dict:
        """
        Returns borehole and section data including hydraulics.

        :param borehole_id: PublicID of the borehole.
        :param section_id:  PublicID of the section.
        :param starttime:   Datetime from when on the data should be retrieved.
        :param endtime:     Datetime until when the data should be retrieved.

        :returns: Borehole and section metadata as well as section hydraulics.
        """

        hydraulics = self.get_section_hydraulics(
            borehole_id, section_id, starttime, endtime)

        request_url = f'{self.url}/boreholes/{borehole_id}'

        metadata = self._make_api_request(request_url, {'level': 'section'})

        metadata['sections'] = [section for section in metadata['sections']
                                if section['publicid'] == section_id]

        if not metadata['sections']:
            raise KeyError(f'Section {section_id} could not be found in '
                           'borehole {borehole_id}')

        metadata['sections'][0]['hydraulics'] = hydraulics
        return metadata

    def get_section_by_name(
            self,
            borehole_name: str,
            section_name: str,
            starttime: datetime,
            endtime: datetime = datetime.now()) -> dict:
        """
        Returns borehole and section data including hydraulics.

        :param borehole_name: Name of the borehole.
        :param section_name:  Name of the section.
        :param starttime:     Datetime from when the data should be retrieved.
        :param endtime:       Datetime until when the data should be retrieved.

        :returns: Borehole and section metadata as well as section hydraulics.
        """
        metadata = self.list_boreholes()
        borehole = next((borehole for borehole in metadata if borehole['name']
                         == borehole_name), None)
        section = next(
            (section for section in borehole['sections'] if section['name']
             == section_name), None)
        return self.get_section(
            borehole['publicid'], section['publicid'], starttime, endtime)

    def get_section_hydraulics(self, borehole_id: str,
                               section_id: str,
                               starttime: datetime,
                               endtime: datetime = datetime.now()) -> list:
        """
        Get section hydraulics without any metadata.

        :param borehole:    PublicID of the borehole.
        :param section:     PublicID of the section.
        :param starttime:   Datetime from when on the data should be retrieved.
        :param endtime:     Datetime until when the data should be retrieved.

        :returns: List of hydraulic samples for the specified parameters.
        """

        params = {
            'starttime': starttime.strftime("%Y-%m-%dT%H:%M:%S"),
            'endtime': endtime.strftime("%Y-%m-%dT%H:%M:%S")}

        self.logger.info(
            f"Request borehole / hydraulic data from hydws (url={self.url}, "
            f"borehole={borehole_id}, section={section_id}, params={params}).")

        request_url = \
            f'{self.url}/boreholes/{borehole_id}/' \
            f'sections/{section_id}/hydraulics'

        return self._make_api_request(request_url, params)

    def get_section_hydraulics_by_name(self,
                                       borehole_name: str,
                                       section_name: str,
                                       starttime: datetime,
                                       endtime: datetime = datetime.now()
                                       ) -> list:
        """
        Get section hydraulics without any metadata.

        :param borehole_name: Name of the borehole.
        :param section_name:  Name of the section.
        :param starttime:     Datetime from when the data should be retrieved.
        :param endtime:       Datetime until when the data should be retrieved.

        :returns: List of hydraulic samples for the specified parameters.
        """
        metadata = self.list_boreholes()
        borehole = next((borehole for borehole in metadata if borehole['name']
                         == borehole_name), None)
        section = next(
            (section for section in borehole['sections'] if section['name']
                == section_name), None)
        return self.get_section_hydraulics(
            borehole['publicid'], section['publicid'], starttime, endtime)

    def _make_api_request(self, request_url: str, params: dict = {}):
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
            self.logger.warning('No data received.')
            return {}
        except RequestsError as err:
            self.logger.error(f"Request Error while fetching data ({err}).")
        except BaseException as err:
            self.logger.error(f"Error while fetching data {err}")
        else:
            self.logger.info('HYDWS data received.')
            return json.loads(response)
