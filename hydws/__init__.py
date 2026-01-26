import logging

import requests

logger = logging.getLogger(__name__)


class RequestsError(requests.exceptions.RequestException):
    """Base request error ({})."""


class NoContent(RequestsError):
    """The request '{}' is returning no content ({})."""


class ClientError(RequestsError):
    """Response code not OK ({})."""


def make_request(request, url, params={}, timeout=None,
                 nocontent_codes=(204,), success_codes=(200,), **kwargs):
    """
    Make a normal request

    :param request: Request object to be used
    :type request: :py:class:`requests.Request`
    :param str url: URL
    :params dict params: Dictionary of query parameters
    :param timeout: Request timeout
    :type timeout: None or int or tuple
    :param nocontent_codes: Status codes that indicate no content
    :param success_codes: Status codes that indicate success

    :return: content of response
    :rtype: string
    """
    try:
        r = request(url, params=params, timeout=timeout, **kwargs)

        logger.debug(f'Making request to {url} with parameters {params}')

        if r.status_code in nocontent_codes:
            raise NoContent(r.url, r.status_code, response=r)

        r.raise_for_status()
        if r.status_code not in success_codes:
            raise ClientError(r.status_code, response=r)

        return r.content

    except (NoContent, ClientError) as err:
        raise err
    except requests.exceptions.RequestException as err:
        raise RequestsError(err, response=err.response)
