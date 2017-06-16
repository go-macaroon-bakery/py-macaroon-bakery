# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
import requests
from six.moves.http_cookiejar import Cookie
from six.moves.urllib.parse import urljoin
from six.moves.urllib.parse import urlparse

from macaroonbakery.bakery import discharge_all
from macaroonbakery import utils

ERR_INTERACTION_REQUIRED = 'interaction required'
ERR_DISCHARGE_REQUIRED = 'macaroon discharge required'
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
    def __init__(self, visit_page=None, key=None,
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
        if visit_page is None:
            visit_page = utils.visit_page_with_browser
        if 'agent-login' in cookies.keys():
            self._visit_page = _visit_page_for_agent(cookies, key)
        else:
            self._visit_page = visit_page
        self._jar = cookies
        self._key = key

    def __call__(self, req):
        req.headers['Bakery-Protocol-Version'] = '1'
        hook = _prepare_discharge_hook(req.copy(), self._key, self._jar,
                                       self._visit_page)
        req.register_hook(event='response', hook=hook)
        return req


def _prepare_discharge_hook(req, key, jar, visit_page):
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
        status_401 = (response.status_code == 401
                      and response.headers.get('WWW-Authenticate') ==
                      'Macaroon')
        if not status_401 and response.status_code != 407:
            return response
        if response.headers.get('Content-Type') != 'application/json':
            return response

        try:
            error = response.json()
        except:
            raise BakeryException(
                'unable to read discharge error response')
        if error.get('Code') != ERR_DISCHARGE_REQUIRED:
            return response
        Retry.count += 1
        if Retry.count > MAX_DISCHARGE_RETRIES:
            raise BakeryException('too many discharges')
        info = error.get('Info')
        if not isinstance(info, dict):
            raise BakeryException(
                'unable to read info in discharge error response')
        serialized_macaroon = info.get('Macaroon')
        if not isinstance(serialized_macaroon, dict):
            raise BakeryException(
                'unable to read macaroon in discharge error response')

        macaroon = utils.deserialize(serialized_macaroon)
        discharges = discharge_all(macaroon, visit_page, jar, key)
        encoded_discharges = map(utils.serialize_macaroon_string, discharges)

        macaroons = '[' + ','.join(encoded_discharges) + ']'
        all_macaroons = base64.urlsafe_b64encode(
            macaroons.encode('utf-8')).decode('ascii')

        full_path = urljoin(response.url,
                            info['MacaroonPath'])
        parsed_url = urlparse(full_path)
        if info and info.get('CookieNameSuffix'):
            name = 'macaroon-' + info['CookieNameSuffix']
        else:
            name = 'macaroon-' + discharges[0].signature
        cookie = Cookie(
            version=0,
            name=name,
            value=all_macaroons,
            port=None,
            port_specified=False,
            domain=parsed_url[1],
            domain_specified=True,
            domain_initial_dot=False,
            path=parsed_url[2],
            path_specified=True,
            secure=False,
            expires=None,
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
        req.headers['Bakery-Protocol-Version'] = '1'
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
