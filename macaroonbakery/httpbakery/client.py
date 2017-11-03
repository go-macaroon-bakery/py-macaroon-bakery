# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import base64
import json
import requests
from six.moves.http_cookies import SimpleCookie
from six.moves.urllib.parse import urljoin

import macaroonbakery as bakery
import macaroonbakery.checkers as checkers
from macaroonbakery import utils
from macaroonbakery.httpbakery.interactor import (
    LegacyInteractor,
    WEB_BROWSER_INTERACTION_KIND,
)
from macaroonbakery.httpbakery.error import (
    DischargeError,
    ERR_DISCHARGE_REQUIRED,
    ERR_INTERACTION_REQUIRED,
    Error,
    InteractionError,
    InteractionMethodNotFound,
)
from macaroonbakery.httpbakery.error import BAKERY_PROTOCOL_HEADER
from macaroonbakery.httpbakery.browser import WebBrowserInteractor

TIME_OUT = 30
MAX_DISCHARGE_RETRIES = 3


class BakeryException(requests.RequestException):
    '''Raised when some errors happen using the httpbakery
    authorizer'''


class Client:
    '''Client holds the context for making HTTP requests with macaroons.
    To make a request, use the auth method to obtain
    an HTTP authorizer suitable for passing as the auth parameter
    to a requests method. Note that the same cookie jar
    should be passed to requests as is used to initialize
    the client.
    For example:
        import macaroonbakery.httpbakery
        client = httpbakery.Client()
        resp = requests.get('some protected url',
                            cookies=client.cookies,
                            auth=client.auth())
    @param interaction_methods A list of Interactor implementations.
    @param key The private key of the client {bakery.PrivateKey}
    @param cookies storage for the cookies {CookieJar}. It should be the
    same as in the requests cookies. If not provided, one
    will be created.
    '''
    def __init__(self, interaction_methods=None, key=None, cookies=None):
        if interaction_methods is None:
            interaction_methods = [WebBrowserInteractor()]
        if cookies is None:
            cookies = requests.cookies.RequestsCookieJar()
        self._interaction_methods = interaction_methods
        self._key = key
        self.cookies = cookies

    def auth(self):
        '''Return an authorizer object suitable for passing
        to requests methods that accept one.
        If a request returns a discharge-required error,
        the authorizer will acquire discharge macaroons
        and retry the request.
        '''
        return _BakeryAuth(self)

    def request(self, method, url, **kwargs):
        '''Use the requests library to make a request.
        Using this method is like doing:

            requests.request(method, url, auth=client.auth())
        '''
        kwargs.setdefault('auth', self.auth())
        return requests.request(method=method, url=url, **kwargs)

    def handle_error(self, error, url):
        '''Try to resolve the given error, which should be a response
        to the given URL, by discharging any macaroon contained in
        it. That is, if error.code is ERR_DISCHARGE_REQUIRED
        then it will try to discharge err.info.macaroon. If the discharge
        succeeds, the discharged macaroon will be saved to the client's cookie jar,
        otherwise an exception will be raised.
        '''
        if error.info is None or error.info.macaroon is None:
            raise BakeryException('unable to read info in discharge error response')

        discharges = bakery.discharge_all(
            error.info.macaroon,
            self.acquire_discharge,
            self._key,
        )
        macaroons = '[' + ','.join(map(utils.macaroon_to_json_string, discharges)) + ']'
        all_macaroons = base64.urlsafe_b64encode(utils.to_bytes(macaroons))

        full_path = relative_url(url, error.info.macaroon_path)
        if error.info.cookie_name_suffix is not None:
            name = 'macaroon-' + error.info.cookie_name_suffix
        else:
            name = 'macaroon-auth'
        expires = checkers.macaroons_expiry_time(checkers.Namespace(), discharges)
        expires = None		# TODO(rogpeppe) remove this line after fixing the tests.
        self.cookies.set_cookie(utils.cookie(
            name=name,
            value=all_macaroons.decode('ascii'),
            url=full_path,
            expires=expires,
        ))

    def acquire_discharge(self, cav, payload):
        ''' Request a discharge macaroon from the caveat location
        as an HTTP URL.
        @param cav Third party {pymacaroons.Caveat} to be discharged.
        @param payload External caveat data {bytes}.
        @return The acquired macaroon {macaroonbakery.Macaroon}
        '''
        resp = self._acquire_discharge_with_token(cav, payload, None)
        # TODO Fabrice what is the other http response possible ??
        if resp.status_code == 200:
            return bakery.Macaroon.from_dict(resp.json().get('Macaroon'))
        cause = Error.from_dict(resp.json())
        if cause.code != ERR_INTERACTION_REQUIRED:
            raise DischargeError(cause.message)
        if cause.info is None:
            raise DischargeError(
                'interaction-required response with no info: {}'.format(resp.json())
            )
        loc = cav.location
        if not loc.endswith('/'):
            loc = loc + '/'
        token, m = self._interact(loc, cause, payload)
        if m is not None:
            # We've acquired the macaroon directly via legacy interaction.
            return m
        # Try to acquire the discharge again, but this time with
        # the token acquired by the interaction method.
        resp = self._acquire_discharge_with_token(cav, payload, token)
        if resp.status_code == 200:
            return bakery.Macaroon.deserialize_json(
                resp.json().get('Macaroon'))
        else:
            raise DischargeError()

    def _acquire_discharge_with_token(self, cav, payload, token):
        req = {}
        _add_json_binary_field(cav.caveat_id_bytes, req, 'id')
        if token is not None:
            _add_json_binary_field(token.value, req, 'token')
            req['token-kind'] = token.kind
        if payload is not None:
            req['caveat64'] = base64.urlsafe_b64encode(payload).rstrip(
                b'=').decode('utf-8')
        target = relative_url(cav.location, 'discharge')
        headers = {
            BAKERY_PROTOCOL_HEADER: str(bakery.LATEST_VERSION)
        }
        return self.request('POST', target, data=req, headers=headers)

    def _interact(self, location, error_info, payload):
        '''Gathers a macaroon by directing the user to interact with a
        web page. The error_info argument holds the interaction-required
        error response.
        @return DischargeToken, bakery.Macaroon
        '''
        if self._interaction_methods is None or len(self._interaction_methods) == 0:
            raise InteractionError('interaction required but not possible')
        # TODO(rogpeppe) make the robust against a wider range of error info.
        if error_info.info.interaction_methods is None and \
                error_info.info.visit_url is not None:
            # It's an old-style error; deal with it differently.
            return None, self._legacy_interact(location, error_info)

        for interactor in self._interaction_methods:
            found = error_info.info.interaction_methods.get(interactor.kind())
            if found is None:
                continue
            try:
                token = interactor.interact(self, location, error_info)
            except InteractionMethodNotFound:
                continue
            if token is None:
                raise InteractionError('interaction method returned an empty token')
            return token, None

        raise InteractionError('no supported interaction method')

    def _legacy_interact(self, location, error_info):
        visit_url = relative_url(location, error_info.info.visit_url)
        wait_url = relative_url(location, error_info.info.wait_url)
        method_urls = {
            "interactive": visit_url
        }
        if len(self._interaction_methods) > 1 or \
                self._interaction_methods[0].kind() != WEB_BROWSER_INTERACTION_KIND:
            # We have several possible methods or we only support a non-window
            # method, so we need to fetch the possible methods supported by
            # the discharger.
            method_urls = _legacy_get_interaction_methods(visit_url)

        for interactor in self._interaction_methods:
            kind = interactor.kind()
            if kind == WEB_BROWSER_INTERACTION_KIND:
                # This is the old name for browser-window interaction.
                kind = "interactive"

            if not isinstance(interactor, LegacyInteractor):
                # Legacy interaction mode isn't supported.
                continue

            visit_url = method_urls.get(kind)
            if visit_url is None:
                continue

            visit_url = relative_url(location, visit_url)
            interactor.legacy_interact(self, location, visit_url)
            return _wait_for_macaroon(wait_url)

        raise InteractionError('no methods supported')


class _BakeryAuth:
    '''_BakeryAuth implements an authorizer as required
    by the requests HTTP client.
    '''
    def __init__(self, client):
        '''
        @param interaction_methods A list of Interactor implementations.
        @param key The private key of the client (macaroonbakery.PrivateKey)
        @param cookies storage for the cookies {CookieJar}. It should be the
        same as in the requests cookies.
        '''
        self._client = client

    def __call__(self, req):
        req.headers[BAKERY_PROTOCOL_HEADER] = str(bakery.LATEST_VERSION)
        hook = _prepare_discharge_hook(req.copy(), self._client)
        req.register_hook(event='response', hook=hook)
        return req


def _prepare_discharge_hook(req, client):
    ''' Return the hook function (called when the response is received.)

    This allows us to intercept the response and do any necessary
    macaroon discharge before returning.
    '''
    class Retry:
        # Define a local class so that we can use its class variable as
        # mutable state accessed by the closures below.
        count = 0

    def hook(response, *args, **kwargs):
        ''' Requests hooks system, this is the hook for the response.
        '''
        status_code = response.status_code

        if status_code != 407 and status_code != 401:
            return response
        if (status_code == 401 and response.headers.get('WWW-Authenticate') !=
                'Macaroon'):
            return response

        if response.headers.get('Content-Type') != 'application/json':
            return response
        errorJSON = response.json()
        if errorJSON.get('Code') != ERR_DISCHARGE_REQUIRED:
            return response
        error = Error.from_dict(errorJSON)
        Retry.count += 1
        if Retry.count >= MAX_DISCHARGE_RETRIES:
            raise BakeryException('too many ({}) discharge requests'.format(
                Retry.count)
            )
        client.handle_error(error, req.url)
        # Replace the private _cookies from req as it is a copy of
        # the original cookie jar passed into the requests method and we need
        # to set the cookie for this request.
        req._cookies = client.cookies
        req.headers.pop('Cookie', None)
        req.prepare_cookies(req._cookies)
        req.headers[BAKERY_PROTOCOL_HEADER] = \
            str(bakery.LATEST_VERSION)
        with requests.Session() as s:
            return s.send(req)
    return hook


def extract_macaroons(headers):
    ''' Returns an array of any macaroons found in the given slice of cookies.
    @param headers: dict of headers
    @return: An array of array of mpy macaroons
    '''
    mss = []

    def add_macaroon(data):
        data = utils.b64decode(data)
        data_as_objs = json.loads(data.decode('utf-8'))
        ms = [utils.macaroon_from_dict(x) for x in data_as_objs]
        mss.append(ms)

    cookieHeader = headers.get('Cookie')
    if cookieHeader is not None:
        cs = SimpleCookie()
        # The cookie might be a unicode object, so convert it
        # to ASCII. This may cause an exception under Python 2.
        # TODO is that a problem?
        cs.load(str(cookieHeader))
        for c in cs:
            if c.startswith('macaroon-'):
                add_macaroon(cs[c].value)
    # Python doesn't make it easy to have multiple values for a
    # key, so split the header instead, which is necessary
    # for HTTP1.1 compatibility anyway.
    macaroonHeader = headers.get('Macaroons')
    if macaroonHeader is not None:
        for h in macaroonHeader.split(','):
            add_macaroon(h)
    return mss


def _add_json_binary_field(b, serialized, field):
    '''' Set the given field to the given val (bytes) in the serialized
    dictionary.
    If the value isn't valid utf-8, we base64 encode it and use field+"64"
    as the field name.
    '''
    try:
        val = b.decode('utf-8')
        serialized[field] = val
    except UnicodeDecodeError:
        val = base64.b64encode(b).decode('utf-8')
        serialized[field + '64'] = val


def _wait_for_macaroon(wait_url):
    ''' Returns a macaroon from a legacy wait endpoint.
    '''
    headers = {
        BAKERY_PROTOCOL_HEADER: str(bakery.LATEST_VERSION)
    }
    resp = requests.get(url=wait_url, headers=headers)
    if resp.status_code != 200:
        return InteractionError('cannot get {}'.format(wait_url))

    return bakery.Macaroon.from_dict(resp.json().get('Macaroon'))


def relative_url(base, new):
    ''' Returns new path relative to an original URL.
    '''
    if new == '':
        return base
    if not base.endswith('/'):
        base += '/'
    return urljoin(base, new)


def _legacy_get_interaction_methods(u):
    ''' Queries a URL as found in an ErrInteractionRequired VisitURL field to
    find available interaction methods.
    It does this by sending a GET request to the URL with the Accept
    header set to "application/json" and parsing the resulting
    response as a dict.
    '''
    headers = {
        BAKERY_PROTOCOL_HEADER: str(bakery.LATEST_VERSION),
        'Accept': 'application/json'
    }
    resp = requests.get(url=u, headers=headers)
    method_urls = {}
    if resp.status_code == 200:
        json_resp = resp.json()
        for m in json_resp:
            relative_url(u, json_resp[m])
        method_urls[m] = relative_url(u, json_resp[m])

    if method_urls.get('interactive') is None:
        # There's no "interactive" method returned, but we know
        # the server does actually support it, because all dischargers
        # are required to, so fill it in with the original URL.
        method_urls['interactive'] = u
    return method_urls
