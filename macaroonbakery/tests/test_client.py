# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import base64
import datetime
import json
from unittest import TestCase
try:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from httmock import (
    HTTMock,
    urlmatch
)
import requests
from six.moves.urllib.parse import parse_qs

import macaroonbakery
from macaroonbakery import httpbakery
from macaroonbakery import checkers

AGES = datetime.datetime.utcnow() + datetime.timedelta(days=1)
TEST_OP = macaroonbakery.Op(entity='test', action='test')


class TestClient(TestCase):
    def test_single_service_first_party(self):
        b = new_bakery('loc', None, None)

        def handler(*args):
            GetHandler(b, None, None, None, None, *args)
        try:
            httpd = HTTPServer(('', 0), handler)
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            srv_macaroon = b.oven.macaroon(
                version=macaroonbakery.LATEST_BAKERY_VERSION, expiry=AGES,
                caveats=None, ops=[TEST_OP])
            self.assertEquals(srv_macaroon.macaroon.location, 'loc')
            cookies = requests.cookies.RequestsCookieJar()
            cookie = requests.cookies.create_cookie(
                'macaroon-test', base64.b64encode(json.dumps([
                    srv_macaroon.to_dict().get('m')
                ]).encode('utf-8')).decode('utf-8')
            )
            cookies.set_cookie(cookie)
            resp = requests.get(
                url='http://' + httpd.server_address[0] + ':' +
                    str(httpd.server_address[1]),
                cookies=cookies, auth=httpbakery.BakeryAuth(cookies=cookies))
            resp.raise_for_status()
            self.assertEquals(resp.text, 'done')
        finally:
            httpd.shutdown()

    def test_single_party_with_header(self):
        b = new_bakery('loc', None, None)

        def handler(*args):
            GetHandler(b, None, None, None, None, *args)
        try:
            httpd = HTTPServer(('', 0), handler)
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            srv_macaroon = b.oven.macaroon(
                version=macaroonbakery.LATEST_BAKERY_VERSION,
                expiry=AGES, caveats=None, ops=[TEST_OP])
            self.assertEquals(srv_macaroon.macaroon.location, 'loc')
            headers = {
                'Macaroons': base64.b64encode(json.dumps([
                    srv_macaroon.to_dict().get('m')
                ]).encode('utf-8'))
            }
            resp = requests.get(
                url='http://' + httpd.server_address[0] + ':' +
                    str(httpd.server_address[1]),
                headers=headers)
            resp.raise_for_status()
            self.assertEquals(resp.text, 'done')
        finally:
            httpd.shutdown()

    def test_repeated_request_with_body(self):
        class _DischargerLocator(macaroonbakery.ThirdPartyLocator):
            def __init__(self):
                self.key = macaroonbakery.generate_key()

            def third_party_info(self, loc):
                if loc == 'http://1.2.3.4':
                    return macaroonbakery.ThirdPartyInfo(
                        public_key=self.key.public_key,
                        version=macaroonbakery.LATEST_BAKERY_VERSION,
                    )

        d = _DischargerLocator()
        b = new_bakery('loc', d, None)

        @urlmatch(path='.*/discharge')
        def discharge(url, request):
            qs = parse_qs(request.body)
            content = {q: qs[q][0] for q in qs}
            m = httpbakery.discharge(checkers.AuthContext(), content, d.key,
                                     d, None)
            return {
                'status_code': 200,
                'content': {
                    'Macaroon': m.to_dict()
                }
            }

        def handler(*args):
            GetHandler(b, 'http://1.2.3.4', None, None, None, *args)
        try:
            httpd = HTTPServer(('', 0), handler)
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            jar = requests.cookies.RequestsCookieJar()
            with HTTMock(discharge):
                resp = requests.get(
                    url='http://' + httpd.server_address[0] + ':' +
                        str(httpd.server_address[1]),
                    cookies=jar,
                    auth=httpbakery.BakeryAuth(cookies=jar))
            resp.raise_for_status()
            self.assertEquals(resp.text, 'done')
        finally:
            httpd.shutdown()

    def test_too_many_discharge(self):
        class _DischargerLocator(macaroonbakery.ThirdPartyLocator):
            def __init__(self):
                self.key = macaroonbakery.generate_key()

            def third_party_info(self, loc):
                if loc == 'http://1.2.3.4':
                    return macaroonbakery.ThirdPartyInfo(
                        public_key=self.key.public_key,
                        version=macaroonbakery.LATEST_BAKERY_VERSION,
                    )

        d = _DischargerLocator()
        b = new_bakery('loc', d, None)

        @urlmatch(path='.*/discharge')
        def discharge(url, request):
            wrong_macaroon = macaroonbakery.Macaroon(
                root_key=b'some key', id=b'xxx',
                location='some other location',
                version=macaroonbakery.BAKERY_V0)
            return {
                'status_code': 200,
                'content': {
                    'Macaroon': wrong_macaroon.to_dict()
                }
            }

        def handler(*args):
            GetHandler(b, 'http://1.2.3.4', None, None, None, *args)
        try:
            httpd = HTTPServer(('', 0), handler)
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            jar = requests.cookies.RequestsCookieJar()
            with HTTMock(discharge):
                with self.assertRaises(httpbakery.BakeryException) as ctx:
                    requests.get(
                        url='http://' + httpd.server_address[0] + ':' +
                            str(httpd.server_address[1]),
                        cookies=jar,
                        auth=httpbakery.BakeryAuth(cookies=jar))
            self.assertEqual(ctx.exception.args[0],
                             'too many (3) discharge requests')
        finally:
            httpd.shutdown()

    def test_third_party_discharge_refused(self):
        class _DischargerLocator(macaroonbakery.ThirdPartyLocator):
            def __init__(self):
                self.key = macaroonbakery.generate_key()

            def third_party_info(self, loc):
                if loc == 'http://1.2.3.4':
                    return macaroonbakery.ThirdPartyInfo(
                        public_key=self.key.public_key,
                        version=macaroonbakery.LATEST_BAKERY_VERSION,
                    )

        def check(cond, arg):
            raise macaroonbakery.ThirdPartyCaveatCheckFailed(
                'boo! cond' + cond)

        class ThirdPartyCaveatCheckerF(
                macaroonbakery.ThirdPartyCaveatChecker):
            def check_third_party_caveat(self, ctx, info):
                cond, arg = checkers.parse_caveat(
                    info.condition)
                return check(cond, arg)
        d = _DischargerLocator()
        b = new_bakery('loc', d, None)

        @urlmatch(path='.*/discharge')
        def discharge(url, request):
            qs = parse_qs(request.body)
            content = {q: qs[q][0] for q in qs}
            httpbakery.discharge(checkers.AuthContext(), content, d.key, d,
                                 ThirdPartyCaveatCheckerF())

        def handler(*args):
            GetHandler(b, 'http://1.2.3.4', None, None, None, *args)
        try:
            httpd = HTTPServer(('', 0), handler)
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            jar = requests.cookies.RequestsCookieJar()
            with HTTMock(discharge):
                with self.assertRaises(
                        macaroonbakery.ThirdPartyCaveatCheckFailed):
                    requests.get(
                        url='http://' + httpd.server_address[0] + ':' +
                            str(httpd.server_address[1]),
                        cookies=jar,
                        auth=httpbakery.BakeryAuth(cookies=jar))
        finally:
            httpd.shutdown()

    def test_discharge_with_interaction_required_error(self):
        class _DischargerLocator(macaroonbakery.ThirdPartyLocator):
            def __init__(self):
                self.key = macaroonbakery.generate_key()

            def third_party_info(self, loc):
                if loc == 'http://1.2.3.4':
                    return macaroonbakery.ThirdPartyInfo(
                        public_key=self.key.public_key,
                        version=macaroonbakery.LATEST_BAKERY_VERSION,
                    )
        d = _DischargerLocator()
        b = new_bakery('loc', d, None)

        @urlmatch(path='.*/discharge')
        def discharge(url, request):
            return {
                'status_code': 401,
                'content': {
                    'Code': httpbakery.ERR_INTERACTION_REQUIRED,
                    'Message': 'interaction required',
                    'Info': {
                        'WaitURL': 'http://0.1.2.3/',
                        'VisitURL': 'http://0.1.2.3/',
                    },
                }
            }

        def handler(*args):
            GetHandler(b, 'http://1.2.3.4', None, None, None, *args)

        try:
            httpd = HTTPServer(('', 0), handler)
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            jar = requests.cookies.RequestsCookieJar()

            class MyInteractor(httpbakery.LegacyInteractor):
                def legacy_interact(self, ctx, location, visit_url):
                    raise httpbakery.InteractionError('cannot visit')

                def interact(self, ctx, location, interaction_required_err):
                    pass

                def kind(self):
                    return httpbakery.WEB_BROWSER_INTERACTION_KIND

            with HTTMock(discharge):
                with self.assertRaises(httpbakery.InteractionError):
                    requests.get(
                        'http://' + httpd.server_address[0] + ':' + str(
                            httpd.server_address[1]),
                        cookies=jar,
                        auth=httpbakery.BakeryAuth(
                            cookies=jar,
                            interaction_methods=[MyInteractor()]))
        finally:
            httpd.shutdown()


class GetHandler(BaseHTTPRequestHandler):
    def __init__(self, bakery, auth_location, mutate_error,
                 caveats, version, *args):
        '''
        :param: bakery used to check incoming requests and macaroons
        for discharge-required errors.
        :param: auth_location holds the location of any 3rd party
        authorizer. If this is not None, a 3rd party caveat will be
        added addressed to this location.
        :param: mutate_error if non None, will be called with any
        discharge-required error before responding to the client.
        :param: caveats called to get caveats to add to the returned
        macaroon.
        :param: holds the version of the bakery that the
        // server will purport to serve.
        '''
        self._bakery = bakery
        self._auth_location = auth_location
        self._mutate_error = mutate_error
        self._caveats = caveats
        self._server_version = version
        BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        ctx = checkers.AuthContext()
        auth_checker = self._bakery.checker.auth(
            httpbakery.extract_macaroons(self.headers))
        try:
            auth_checker.allow(ctx, [TEST_OP])
        except (macaroonbakery.PermissionDenied,
                macaroonbakery.VerificationError) as exc:
            return self._write_discharge_error(exc)
        self.send_response(200)
        self.end_headers()
        content_len = int(self.headers.get('content-length', 0))
        content = 'done'
        if self.path != '/no-body'and content_len > 0:
            body = self.rfile.read(content_len)
            content = content + ' ' + body
        self.wfile.write(content.encode('utf-8'))
        return

    def _write_discharge_error(self, exc):
        version = httpbakery.request_version(self.headers)
        if version < macaroonbakery.LATEST_BAKERY_VERSION:
            self._server_version = version

        caveats = []
        if self._auth_location != '':
            caveats = [
                checkers.Caveat(location=self._auth_location,
                                condition='is-ok')
            ]
        if self._caveats is not None:
            caveats.extend(self._caveats)

        m = self._bakery.oven.macaroon(
            version=macaroonbakery.LATEST_BAKERY_VERSION, expiry=AGES,
            caveats=caveats, ops=[TEST_OP])

        content, headers = httpbakery.discharge_required_response(
            m, '/', 'test', exc.args[0])
        self.send_response(401)
        for h in headers:
            self.send_header(h, headers[h])
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(content)


def new_bakery(location, locator, checker):
    if checker is None:
        c = checkers.Checker()
        c.namespace().register('testns', '')
        c.register('is', 'testns', check_is_something)
        checker = c
    key = macaroonbakery.generate_key()
    return macaroonbakery.Bakery(location=location, locator=locator,
                                 key=key, checker=checker)


def is_something_caveat():
    return checkers.Caveat(condition='is something', namespace='testns')


def check_is_something(ctx, cond, arg):
    if arg != 'something':
        return '{} doesn\'t match "something"'.format(arg)
    return None
