import contextlib
import io
import logging

import requests

logger = logging.getLogger(__name__)


class RequestsError(requests.exceptions.RequestException):
    """Base request error ({})."""


class NoContent(RequestsError):
    """The request '{}' is returning no content ({})."""


class ClientError(RequestsError):
    """Response code not OK ({})."""


@contextlib.contextmanager
def binary_request(request, url, params={}, timeout=None,
                   nocontent_codes=(204,), **kwargs):
    """
    Make a binary request

    :param request: Request object to be used
    :type request: :py:class:`requests.Request`
    :param str url: URL
    :params dict params: Dictionary of query parameters
    :param timeout: Request timeout
    :type timeout: None or int or tuple

    :rtype: io.BytesIO
    """
    try:
        r = request(url, params=params, timeout=timeout, **kwargs)
        print("request", r, type(r))
        if r.status_code in nocontent_codes:
            raise NoContent(r.url, r.status_code, response=r)

        r.raise_for_status()
        if r.status_code != 200:
            raise ClientError(r.status_code, response=r)

        yield io.BytesIO(r.content)

    except (NoContent, ClientError) as err:
        raise err
    except requests.exceptions.RequestException as err:
        raise RequestsError(err, response=err.response)


def make_request(request, url, params={}, timeout=None,
                 nocontent_codes=(204,), **kwargs):
    """
    Make a normal request

    :param request: Request object to be used
    :type request: :py:class:`requests.Request`
    :param str url: URL
    :params dict params: Dictionary of query parameters
    :param timeout: Request timeout
    :type timeout: None or int or tuple

    :return: content of response
    :rtype: string
    """
    try:
        r = request(url, params=params, timeout=timeout, **kwargs)

        logger.debug(f'Making request to {url} with parameters {params}')

        if r.status_code in nocontent_codes:
            raise NoContent(r.url, r.status_code, response=r)

        r.raise_for_status()
        if r.status_code != 200:
            raise ClientError(r.status_code, response=r)

        return r.content

    except (NoContent, ClientError) as err:
        raise err
    except requests.exceptions.RequestException as err:
        raise RequestsError(err, response=err.response)
