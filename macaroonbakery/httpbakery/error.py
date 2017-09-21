# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from collections import namedtuple
import json

from macaroonbakery import BAKERY_V1, LATEST_BAKERY_VERSION
from macaroonbakery import Macaroon

ERR_INTERACTION_REQUIRED = 'interaction required'
ERR_DISCHARGE_REQUIRED = 'macaroon discharge required'


class InteractionMethodNotFound(Exception):
    pass


class DischargeError(Exception):
    pass


class InteractionError(Exception):
    pass


class InteractionRequiredError(Exception):
    def __init__(self, error):
        self.error = error


def discharge_required_response(macaroon, path, cookie_suffix_name,
                                message=None):
    ''' Get response content and headers from a discharge macaroons error.

    @param macaroon may hold a macaroon that, when discharged, may
    allow access to a service.
    @param path holds the URL path to be associated with the macaroon.
    The macaroon is potentially valid for all URLs under the given path.
    @param cookie_suffix_name holds the desired cookie name suffix to be
    associated with the macaroon. The actual name used will be
    ("macaroon-" + CookieName). Clients may ignore this field -
    older clients will always use ("macaroon-" + macaroon.signature() in hex)
    @return content(bytes) and the headers to set on the response(dict).
    '''
    if message is None:
        message = 'discharge required'
    content = json.dumps(
        {
            'Code': 'macaroon discharge required',
            'Message': message,
            'Info': {
                'Macaroon': macaroon.to_dict(),
                'MacaroonPath': path,
                'CookieNameSuffix': cookie_suffix_name
            },
        }
    ).encode('utf-8')
    return content, {
        'WWW-Authenticate': 'Macaroon',
        'Content-Type': 'application/json'
    }

# BAKERY_PROTOCOL_HEADER is the header that HTTP clients should set
# to determine the bakery protocol version. If it is 0 or missing,
# a discharge-required error response will be returned with HTTP status 407;
# if it is greater than 0, the response will have status 401 with the
# WWW-Authenticate header set to "Macaroon".
BAKERY_PROTOCOL_HEADER = 'Bakery-Protocol-Version'


def request_version(req_headers):
    ''' Determines the bakery protocol version from a client request.
    If the protocol cannot be determined, or is invalid, the original version
    of the protocol is used. If a later version is found, the latest known
    version is used, which is OK because versions are backwardly compatible.

    @param req_headers: the request headers as a dict.
    @return: bakery protocol version (for example macaroonbakery.BAKERY_V1)
    '''
    vs = req_headers.get(BAKERY_PROTOCOL_HEADER)
    if vs is None:
        # No header - use backward compatibility mode.
        return BAKERY_V1
    try:
        x = int(vs)
    except ValueError:
        # Badly formed header - use backward compatibility mode.
        return BAKERY_V1
    if x > LATEST_BAKERY_VERSION:
        # Later version than we know about - use the
        # latest version that we can.
        return LATEST_BAKERY_VERSION
    return x


class Error(namedtuple('Error', 'code, message, version, info')):
    @classmethod
    def deserialize(cls, serialized):
        code = serialized.get('Code')
        message = serialized.get('Message')
        info = ErrorInfo.deserialize(serialized.get('Info'))
        return Error(code=code, message=message, info=info,
                     version=LATEST_BAKERY_VERSION)

    def interaction_method(self, kind, x):
        ''' Checks whether the error is an InteractionRequired error
        that implements the method with the given name, and JSON-unmarshals the
        method-specific data into x.
        '''
        if self.info is None or self.code != ERR_INTERACTION_REQUIRED:
            raise InteractionError(
                'not an interaction-required error (code {})'.format(
                    self.code)
            )
        entry = self.info.interaction_methods.get(kind)
        if entry is None:
            raise InteractionMethodNotFound(
                'interaction method {} not found'.format(kind)
            )
        return x.deserialize(entry)


class ErrorInfo(
    namedtuple('ErrorInfo', 'macaroon, macaroon_path, cookie_name_suffix, '
                            'interaction_methods, visit_url, wait_url')):
    '''  Holds additional information provided
    by an error.

    @param macaroon may hold a macaroon that, when
    discharged, may allow access to a service.
    This field is associated with the ERR_DISCHARGE_REQUIRED
    error code.

    @ param macaroon_path holds the URL path to be associated
    with the macaroon. The macaroon is potentially
    valid for all URLs under the given path.
    If it is empty, the macaroon will be associated with
    the original URL from which the error was returned.

    @param cookie_name_suffix holds the desired cookie name suffix to be
    associated with the macaroon. The actual name used will be
    ("macaroon-" + cookie_name_suffix). Clients may ignore this field -
    older clients will always use ("macaroon-" +
    macaroon.signature() in hex).

    @param visit_url holds a URL that the client should visit
    in a web browser to authenticate themselves.

    @param wait_url holds a URL that the client should visit
    to acquire the discharge macaroon. A GET on
    this URL will block until the client has authenticated,
    and then it will return the discharge macaroon.
    '''

    __slots__ = ()

    @classmethod
    def deserialize(cls, serialized):
        if serialized is None:
            return None
        macaroon = serialized.get('Macaroon')
        if macaroon is not None:
            macaroon = Macaroon.deserialize_json(macaroon)
        path = serialized.get('MacaroonPath')
        cookie_name_suffix = serialized.get('CookieNameSuffix')
        visit_url = serialized.get('VisitURL')
        wait_url = serialized.get('WaitURL')
        interaction_methods = serialized.get('InteractionMethods')
        return ErrorInfo(macaroon=macaroon, macaroon_path=path,
                         cookie_name_suffix=cookie_name_suffix,
                         visit_url=visit_url, wait_url=wait_url,
                         interaction_methods=interaction_methods)

    def __new__(cls, macaroon=None, macaroon_path=None,
                cookie_name_suffix=None, interaction_methods=None,
                visit_url=None, wait_url=None):
        return super(ErrorInfo, cls).__new__(
            cls, macaroon, macaroon_path, cookie_name_suffix,
            interaction_methods, visit_url, wait_url)
