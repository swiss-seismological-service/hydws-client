import json
import logging
import uuid
from datetime import datetime

import pandas as pd
import requests

from hydws import NoContent, RequestsError, make_request
from hydws.parser import SectionHydraulics


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

        self.metadata = self._make_api_request(f'{self.url}/boreholes')

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

        :param borehole_id: PublicID or name of the borehole.
        :returns:           Borehole data as a dict.
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

        :param borehole_name: PublicID or name of the borehole.
        :param identifier:    'name', 'publicid' or 'both'.

        :returns:             List of sections for the borehole.
        """

        borehole_metadata = self.get_borehole_metadata(borehole)

        return borehole_metadata['sections']

    def list_section_names(self, borehole: str, identifier: str = 'name') \
            -> list[tuple[str, str] | list[str]]:
        """
        Returns a list of all section names and id's for a given borehole.

        :param borehole_name: PublicID or name of the borehole.
        :returns:             List of tuples with section name and id.
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

        :param borehole_id: PublicID or name of the borehole.
        :param starttime:   Datetime from when on the data should be retrieved.
        :param endtime:     Datetime until when the data should be retrieved.

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

        :param borehole_id: PublicID or name of the borehole.
        :param section_id:  PublicID or name of the section.
        :param starttime:   Datetime from when on the data should be retrieved.
        :param endtime:     Datetime until when the data should be retrieved.

        :returns: Section metadata as well as section hydraulics.
        """
        borehole_id = self._get_borehole_id(borehole)
        section_id = self._get_section_id(borehole_id, section)

        section_metadata = self.get_section_metadata(borehole_id, section_id)
        section_hydraulics = self.get_section_hydraulics(
            borehole_id, section_id, starttime, endtime)

        section_metadata['hydraulics'] = section_hydraulics
        return section_metadata

    def get_section_hydraulics(self, borehole: str,
                               section: str,
                               starttime: datetime,
                               endtime: datetime = datetime.now(),
                               format: str = 'json') -> list:
        """
        Get section hydraulics without any metadata.

        :param borehole:    PublicID or name of the borehole.
        :param section:     PublicID or name of the section.
        :param starttime:   Datetime from when on the data should be retrieved.
        :param endtime:     Datetime until when the data should be retrieved.
        :param format:      Format of the returned data, 'json' or 'pandas'.

        :returns: List of hydraulic samples for the specified parameters.
        """
        borehole_id = self._get_borehole_id(borehole)
        section_id = self._get_section_id(borehole_id, section)

        params = {
            'starttime': starttime.strftime("%Y-%m-%dT%H:%M:%S"),
            'endtime': endtime.strftime("%Y-%m-%dT%H:%M:%S")}

        self.logger.info(
            f"Request borehole / hydraulic data from hydws (url={self.url}, "
            f"borehole={borehole_id}, section={section_id}, params={params}).")

        request_url = \
            f'{self.url}/boreholes/{borehole_id}/' \
            f'sections/{section_id}/hydraulics'

        hydraulics = self._make_api_request(request_url, params)

        if format == 'pandas':
            if not hydraulics:
                return pd.DataFrame()
            return SectionHydraulics._load_hydraulic_json(hydraulics)

        if not hydraulics:
            return []

        return hydraulics

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
