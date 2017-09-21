# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import base64
import json
import requests
from six.moves.http_cookies import SimpleCookie
from six.moves.http_cookiejar import Cookie
from six.moves.urllib.parse import urljoin
from six.moves.urllib.parse import urlparse

from pymacaroons.serializers.json_serializer import JsonSerializer
from pymacaroons import Macaroon as PyMacaroon


import macaroonbakery
from macaroonbakery import checkers as checkers
from macaroonbakery import utils, Macaroon
from macaroonbakery.httpbakery.interactor import (
    LegacyInteractor, WEB_BROWSER_INTERACTION_KIND
)
from macaroonbakery.httpbakery.error import (
    Error, ERR_DISCHARGE_REQUIRED, ERR_INTERACTION_REQUIRED, InteractionError,
    DischargeError, InteractionMethodNotFound
)
from macaroonbakery import LATEST_BAKERY_VERSION
from macaroonbakery.httpbakery.error import BAKERY_PROTOCOL_HEADER
from macaroonbakery.httpbakery.browser import WebBrowserInteractor

TIME_OUT = 30
MAX_DISCHARGE_RETRIES = 3


class BakeryAuth:
    ''' BakeryAuth holds the context for making HTTP requests with macaroons.

        This will automatically acquire and discharge macaroons around the
        requests framework.
        Usage:
            from macaroonbakery import httpbakery
            jar = requests.cookies.RequestsCookieJar()
            resp = requests.get('some protected url',
                                cookies=jar,
                                auth=httpbakery.BakeryAuth(cookies=jar))
            resp.raise_for_status()
    '''
    def __init__(self, interaction_methods=None, key=None,
                 cookies=requests.cookies.RequestsCookieJar()):
        '''

        @param visit_page function called when the discharge process requires
        further interaction taking a visit_url string as parameter.
        @param key holds the client's private nacl key. If set, the client
        will try to discharge third party caveats with the special location
        "local" by using this key.
        @param cookies storage for the cookies {CookieJar}. It should be the
        same than in the requests cookies
        '''
        if interaction_methods is None:
            interaction_methods = [WebBrowserInteractor()]
        self._interaction_methods = interaction_methods
        self._jar = cookies
        self._key = key

    def __call__(self, req):
        req.headers[BAKERY_PROTOCOL_HEADER] = str(LATEST_BAKERY_VERSION)
        hook = _prepare_discharge_hook(req.copy(), self._interaction_methods,
                                       self._jar, self._key)
        req.register_hook(event='response', hook=hook)
        return req


def _prepare_discharge_hook(req, interaction_methods, jar, key):
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

        error = response.json()
        code = error.get('Code')
        if code != ERR_DISCHARGE_REQUIRED:
            return response

        Retry.count += 1
        if Retry.count >= MAX_DISCHARGE_RETRIES:
            raise BakeryException('too many ({}) discharge requests'.format(
                Retry.count)
            )
        info = error.get('Info')
        if not isinstance(info, dict):
            raise BakeryException(
                'unable to read info in discharge error response')
        serialized_macaroon = info.get('Macaroon')
        if not isinstance(serialized_macaroon, dict):
            raise BakeryException(
                'unable to read macaroon in discharge error response')

        macaroon = Macaroon.deserialize_json(json.dumps(serialized_macaroon))
        ctx = checkers.AuthContext()
        discharges = macaroonbakery.discharge_all(
            ctx, macaroon, acquire_discharge(interaction_methods), key)
        encoded_discharges = map(utils.serialize_macaroon_string, discharges)

        macaroons = '[' + ','.join(encoded_discharges) + ']'
        all_macaroons = base64.urlsafe_b64encode(
            macaroons.encode('utf-8')).decode('ascii')

        full_path = relative_url(req.url,
                                 info['MacaroonPath'])
        parsed_url = urlparse(full_path)
        if info and info.get('CookieNameSuffix'):
            name = 'macaroon-' + info['CookieNameSuffix']
        else:
            name = 'macaroon-' + discharges[0].signature
        domain = parsed_url.hostname or parsed_url.netloc
        port = str(parsed_url.port) if parsed_url.port is not None else None
        secure = parsed_url.scheme == 'https'
        # expires = checkers.macaroons_expiry_time(
        #     checkers.Namespace(), discharges)
        # expires = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
        expires = None
        cookie = Cookie(
            version=0,
            name=name,
            value=all_macaroons,
            port=port,
            port_specified=port is not None,
            domain=domain,
            domain_specified=True,
            domain_initial_dot=False,
            path=parsed_url.path,
            path_specified=True,
            secure=secure,
            expires=expires,
            discard=False,
            comment=None,
            comment_url=None,
            rest=None,
            rfc2109=False)
        jar.set_cookie(cookie)
        # Replace the private _cookies from req as it is a copy of
        # the original cookie jar passed into the requests method and we need
        # to set the cookie for this request.
        req._cookies = jar
        req.headers.pop('Cookie', None)
        req.prepare_cookies(req._cookies)
        req.headers[BAKERY_PROTOCOL_HEADER] = \
            str(macaroonbakery.LATEST_BAKERY_VERSION)
        with requests.Session() as s:
            return s.send(req)
    return hook


class BakeryException(requests.RequestException):
    ''' Bakery exception '''


def _visit_page_for_agent(cookies, key):
    def visit_page_for_agent(visit_url):
        resp = requests.get(visit_url, cookies=cookies,
                            auth=BakeryAuth(cookies=cookies, key=key))
        resp.raise_for_status()
    return visit_page_for_agent


def extract_macaroons(headers):
    ''' Returns an array of any macaroons found in the given slice of cookies.
    @param headers: dict of headers
    @return: An array of array of mpy macaroons
    '''
    cs = SimpleCookie()
    cookies = headers.get('Cookie')
    mss = []
    if cookies is not None:
        cs.load(str(cookies))
        for c in cs:
            if not c.startswith('macaroon-'):
                continue
            data = base64.b64decode(cs[c].value)
            data_as_objs = json.loads(data.decode('utf-8'))
            ms = [PyMacaroon.deserialize(json.dumps(x),
                                         serializer=JsonSerializer())
                  for x in data_as_objs]
            mss.append(ms)
    macaroons_header = headers.get('Macaroons')
    if macaroons_header is not None:
        data = base64.b64decode(macaroons_header)
        data_as_objs = json.loads(data.decode('utf-8'))
        ms = [PyMacaroon.deserialize(json.dumps(x),
                                     serializer=JsonSerializer())
              for x in data_as_objs]
        mss.append(ms)
    return mss


def acquire_discharge(interaction_methods):
    def f(ctx, cav, payload):
        ''' Requesting a discharge macaroon from the caveat location
        as an HTTP URL.
        :return Macaroon
        '''
        resp = _acquire_discharge_with_token(ctx, cav, payload, None)
        # TODO Fabrice what is the other http response possible ??
        if resp.status_code == 200:
            return macaroonbakery.Macaroon.from_dict(
                resp.json().get('Macaroon'))
        cause = Error.deserialize(resp.json())
        if cause.code != ERR_INTERACTION_REQUIRED:
            raise DischargeError(resp.json())
        if cause.info is None:
            raise DischargeError(
                'interaction-required response with no info: {}'.format(
                    resp.json())
            )
        loc = cav.location
        if not loc.endswith('/'):
            loc = loc + '/'
        token, m = _interact(ctx, loc, cause, payload, interaction_methods)
        if m is not None:
            # We've acquired the macaroon directly via legacy interaction.
            return m
        # Try to acquire the discharge again, but this time with
        # the token acquired by the interaction method.
        resp = _acquire_discharge_with_token(ctx, cav, payload, token)
        if resp.status_code == 200:
            return macaroonbakery.Macaroon.deserialize_json(
                resp.json().get('Macaroon'))
        else:
            raise DischargeError()
    return f


def _acquire_discharge_with_token(ctx, cav, payload, token):
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
        BAKERY_PROTOCOL_HEADER: str(LATEST_BAKERY_VERSION)
    }
    resp = requests.post(url=target, data=req, headers=headers)
    return resp


def _add_json_binary_field(b, serialized, field):
    '''' Set the given field to the given val (bytes) in the serialized
    dictionary.
    If the value isn't valid utf-8, we base64 encode it and use field+"64"
    as the field name.
    '''
    try:
        val = b.decode("utf-8")
        serialized[field] = val
    except UnicodeDecodeError:
        val = base64.b64encode(b).decode('utf-8')
        serialized[field + '64'] = val


def _interact(ctx, location, error_info, payload, interaction_methods):
    '''Gathers a macaroon by directing the user to interact with a
    web page. The error_info argument holds the interaction-required
    error response.
    :return: DischargeToken, Macaroon
    '''
    if interaction_methods is None or len(interaction_methods) == 0:
        raise InteractionError('interaction required but not possible')
    if error_info.info.interaction_methods is None and \
            error_info.info.visit_url is not None:
        # It's an old-style error; deal with it differently.
        m = _legacy_interact(ctx, location, error_info, interaction_methods)
        return None, m

    for interactor in interaction_methods:
        found = error_info.info.interaction_methods.get(interactor.kind())
        if found is not None:
            try:
                token = interactor.interact(ctx, location, error_info)
            except InteractionMethodNotFound:
                continue
            if token is None:
                raise InteractionError(
                    'interaction method returned an empty token')
            return token, None
    raise InteractionError('no supported interaction method')


def _legacy_interact(ctx, location, error_info, interaction_methods):
    visit_url = relative_url(location, error_info.info.visit_url)
    wait_url = relative_url(location, error_info.info.wait_url)
    method_urls = {
        "interactive": visit_url
    }
    if len(interaction_methods) > 1 or \
            interaction_methods[0].kind() != WEB_BROWSER_INTERACTION_KIND:
        # We have several possible methods or we only support a non-window
        # method, so we need to fetch the possible methods supported by
        # the discharger.
        method_urls = _legacy_get_interaction_methods(ctx, visit_url)

    for interactor in interaction_methods:
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
        interactor.legacy_interact(ctx, location, visit_url)
        return _wait_for_macaroon(ctx, wait_url)

    raise InteractionError('no methods supported')


def _wait_for_macaroon(ctx, wait_url):
    ''' Returns a macaroon from a legacy wait endpoint.
    '''
    headers = {
        BAKERY_PROTOCOL_HEADER: str(LATEST_BAKERY_VERSION)
    }
    resp = requests.get(url=wait_url, headers=headers)
    if resp.status_code != 200:
        return InteractionError('cannot get {}'.format(wait_url))

    return Macaroon.from_dict(resp.json().get('Macaroon'))


def relative_url(base, new):
    ''' Returns new path relative to an original URL.
    '''
    if new == '':
        raise ValueError('empty URL')
    if not base.endswith('/'):
        base += '/'
    return urljoin(base, new)


def _legacy_get_interaction_methods(ctx, u):
    ''' Queries a URL as found in an ErrInteractionRequired VisitURL field to
    find available interaction methods.
    It does this by sending a GET request to the URL with the Accept
    header set to "application/json" and parsing the resulting
    response as a dict.
    '''
    headers = {
        BAKERY_PROTOCOL_HEADER: str(LATEST_BAKERY_VERSION),
        'Accept': 'application/json'
    }
    resp = requests.get(url=u, headers=headers)
    method_urls = {}
    if resp.status_code == 200:
        json_resp = resp.json()
        for m in json_resp:
            rel_url = urlparse(json_resp[m])
            if rel_url.scheme == '' or rel_url.netloc == '':
                raise InteractionError(
                    'invalid URL {} for interaction method {}'.format(
                        json_resp[m], m)
                )
            if not u.endswith('/'):
                u = u + '/'
            method_urls[m] = urljoin(u, json_resp[m])

    if method_urls.get('interactive') is None:
        # There's no "interactive" method returned, but we know
        # the server does actually support it, because all dischargers
        # are required to, so fill it in with the original URL.
        method_urls['interactive'] = u
    return method_urls
