# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import base64
from datetime import datetime, timedelta
import json
import os
import tempfile
from unittest import TestCase

import nacl.encoding
import requests.cookies
import six
from six.moves.urllib.parse import parse_qs
from six.moves.http_cookies import SimpleCookie
from httmock import (
    HTTMock,
    urlmatch,
    response
)

import macaroonbakery
from macaroonbakery import httpbakery
from macaroonbakery import checkers


class TestAgents(TestCase):
    def setUp(self):
        fd, filename = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write(agent_file)
        self.agent_filename = filename
        fd, filename = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write(bad_key_agent_file)
        self.bad_key_agent_filename = filename
        fd, filename = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write(no_username_agent_file)
        self.no_username_agent_filename = filename

    def tearDown(self):
        os.remove(self.agent_filename)
        os.remove(self.bad_key_agent_filename)
        os.remove(self.no_username_agent_filename)

    def test_load_agents(self):
        cookies, key = httpbakery.load_agent_file(self.agent_filename)
        self.assertEqual(key.encode(nacl.encoding.Base64Encoder),
                         b'CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJEU=')
        self.assertEqual(
            key.public_key.encode(nacl.encoding.Base64Encoder),
            b'YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=')

        value = cookies.get('agent-login', domain='1.example.com')
        jv = base64.b64decode(value)
        if six.PY3:
            jv = jv.decode('utf-8')
        data = json.loads(jv)
        self.assertEqual(data['username'], 'user-1')
        self.assertEqual(data['public_key'],
                         'YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=')

        value = cookies.get('agent-login', domain='2.example.com',
                            path='/discharger')
        jv = base64.b64decode(value)
        if six.PY3:
            jv = jv.decode('utf-8')
        data = json.loads(jv)
        self.assertEqual(data['username'], 'user-2')
        self.assertEqual(data['public_key'],
                         'YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=')

    def test_load_agents_into_cookies(self):
        cookies = requests.cookies.RequestsCookieJar()
        c1, key = httpbakery.load_agent_file(self.agent_filename,
                                             cookies=cookies)
        self.assertEqual(c1, cookies)
        self.assertEqual(key.encode(nacl.encoding.Base64Encoder),
                         b'CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJEU=')
        self.assertEqual(
            key.public_key.encode(nacl.encoding.Base64Encoder),
            b'YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=')

        value = cookies.get('agent-login', domain='1.example.com')
        jv = base64.b64decode(value)
        if six.PY3:
            jv = jv.decode('utf-8')
        data = json.loads(jv)
        self.assertEqual(data['username'], 'user-1')
        self.assertEqual(data['public_key'],
                         'YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=')

        value = cookies.get('agent-login', domain='2.example.com',
                            path='/discharger')
        jv = base64.b64decode(value)
        if six.PY3:
            jv = jv.decode('utf-8')
        data = json.loads(jv)
        self.assertEqual(data['username'], 'user-2')
        self.assertEqual(data['public_key'],
                         'YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=')

    def test_load_agents_with_bad_key(self):
        with self.assertRaises(httpbakery.AgentFileFormatError):
            httpbakery.load_agent_file(self.bad_key_agent_filename)

    def test_load_agents_with_no_username(self):
        with self.assertRaises(httpbakery.AgentFileFormatError):
            httpbakery.load_agent_file(self.no_username_agent_filename)

    def test_agent_login(self):
        discharge_key = macaroonbakery.generate_key()

        class _DischargerLocator(macaroonbakery.ThirdPartyLocator):
            def third_party_info(self, loc):
                if loc == 'http://0.3.2.1':
                    return macaroonbakery.ThirdPartyInfo(
                        public_key=discharge_key.public_key,
                        version=macaroonbakery.LATEST_BAKERY_VERSION,
                    )
        d = _DischargerLocator()
        server_key = macaroonbakery.generate_key()
        server_bakery = macaroonbakery.Bakery(key=server_key, locator=d)

        @urlmatch(path='.*/here')
        def server_get(url, request):
            ctx = checkers.AuthContext()
            test_ops = [macaroonbakery.Op(entity='test-op', action='read')]
            auth_checker = server_bakery.checker.auth(
                httpbakery.extract_macaroons(request.headers))
            try:
                auth_checker.allow(ctx, test_ops)
                resp = response(status_code=200,
                                content='done')
            except macaroonbakery.PermissionDenied:
                caveats = [
                    checkers.Caveat(location='http://0.3.2.1',
                                    condition='is-ok')
                ]
                m = server_bakery.oven.macaroon(
                    version=macaroonbakery.LATEST_BAKERY_VERSION,
                    expiry=datetime.utcnow() + timedelta(days=1),
                    caveats=caveats, ops=test_ops)
                content, headers = httpbakery.discharge_required_response(
                    m, '/',
                    'test',
                    'message')
                resp = response(status_code=401,
                                content=content,
                                headers=headers)
            return request.hooks['response'][0](resp)

        @urlmatch(path='.*/discharge')
        def discharge(url, request):
            qs = parse_qs(request.body)
            if qs.get('token64') is None:
                return response(
                    status_code=401,
                    content={
                        'Code': httpbakery.ERR_INTERACTION_REQUIRED,
                        'Message': 'interaction required',
                        'Info': {
                            'InteractionMethods': {
                                'agent': {'login-url': '/login'},
                            },
                        },
                    },
                    headers={'Content-Type': 'application/json'})
            else:
                qs = parse_qs(request.body)
                content = {q: qs[q][0] for q in qs}
                m = httpbakery.discharge(checkers.AuthContext(), content,
                                         discharge_key, None, None)
                return {
                    'status_code': 200,
                    'content': {
                        'Macaroon': m.serialize_json()
                    }
                }

        key = macaroonbakery.generate_key()

        @urlmatch(path='.*/login')
        def login(url, request):
            b = macaroonbakery.Bakery(key=discharge_key)
            m = b.oven.macaroon(
                version=macaroonbakery.LATEST_BAKERY_VERSION,
                expiry=datetime.utcnow() + timedelta(days=1),
                caveats=[macaroonbakery.local_third_party_caveat(
                    key.public_key,
                    version=httpbakery.request_version(request.headers))],
                ops=[macaroonbakery.Op(entity='agent', action='login')])
            return {
                'status_code': 200,
                'content': {
                    'macaroon': m.to_dict()
                }
            }

        with HTTMock(server_get):
            with HTTMock(discharge):
                with HTTMock(login):
                        resp = requests.get(
                            'http://0.1.2.3/here',
                            auth=httpbakery.BakeryAuth(
                                interaction_methods=[
                                    httpbakery.AgentInteractor(
                                        httpbakery.AuthInfo(
                                            key=key,
                                            agents=[
                                                httpbakery.Agent(
                                                    username='test-user',
                                                    url=u'http://0.3.2.1')
                                            ]))
                                ]))
        self.assertEquals(resp.content, b'done')

    def test_agent_legacy(self):
        discharge_key = macaroonbakery.generate_key()

        class _DischargerLocator(macaroonbakery.ThirdPartyLocator):
            def third_party_info(self, loc):
                if loc == 'http://0.3.2.1':
                    return macaroonbakery.ThirdPartyInfo(
                        public_key=discharge_key.public_key,
                        version=macaroonbakery.LATEST_BAKERY_VERSION,
                    )
        d = _DischargerLocator()
        server_key = macaroonbakery.generate_key()
        server_bakery = macaroonbakery.Bakery(key=server_key, locator=d)

        @urlmatch(path='.*/here')
        def server_get(url, request):
            ctx = checkers.AuthContext()
            test_ops = [macaroonbakery.Op(entity='test-op', action='read')]
            auth_checker = server_bakery.checker.auth(
                httpbakery.extract_macaroons(request.headers))
            try:
                auth_checker.allow(ctx, test_ops)
                resp = response(status_code=200,
                                content='done')
            except macaroonbakery.PermissionDenied:
                caveats = [
                    checkers.Caveat(location='http://0.3.2.1',
                                    condition='is-ok')
                ]
                m = server_bakery.oven.macaroon(
                    version=macaroonbakery.LATEST_BAKERY_VERSION,
                    expiry=datetime.utcnow() + timedelta(days=1),
                    caveats=caveats, ops=test_ops)
                content, headers = httpbakery.discharge_required_response(
                    m, '/',
                    'test',
                    'message')
                resp = response(status_code=401,
                                content=content,
                                headers=headers)
            return request.hooks['response'][0](resp)

        class InfoStorage:
            info = None

        @urlmatch(path='.*/discharge')
        def discharge(url, request):
            qs = parse_qs(request.body)
            if qs.get('caveat64') is not None:
                content = {q: qs[q][0] for q in qs}

                class CheckerInError(macaroonbakery.ThirdPartyCaveatChecker):
                    def check_third_party_caveat(self, ctx, info):
                        InfoStorage.info = info
                        raise httpbakery.InteractionRequiredError(
                            httpbakery.Error(
                                code=httpbakery.ERR_INTERACTION_REQUIRED,
                                version=httpbakery.request_version(
                                    request.headers),
                                message='interaction required',
                                info=httpbakery.ErrorInfo(
                                    wait_url='http://0.3.2.1/wait?'
                                             'dischargeid=1',
                                    visit_url='http://0.3.2.1/visit?'
                                              'dischargeid=1'
                                ))
                            )
                try:
                    httpbakery.discharge(
                        checkers.AuthContext(), content,
                        discharge_key, None, CheckerInError())
                except httpbakery.InteractionRequiredError as exc:
                    return response(
                        status_code=401,
                        content={
                            'Code': exc.error.code,
                            'Message': exc.error.message,
                            'Info': {
                                'WaitURL': exc.error.info.wait_url,
                                'VisitURL': exc.error.info.visit_url,
                            },
                        },
                        headers={'Content-Type': 'application/json'})

        key = macaroonbakery.generate_key()

        @urlmatch(path='.*/visit?$')
        def visit(url, request):
            if request.headers.get('Accept') == 'application/json':
                return {
                    'status_code': 200,
                    'content': {
                        'agent': request.url
                    }
                }
            cs = SimpleCookie()
            cookies = request.headers.get('Cookie')
            if cookies is not None:
                cs.load(str(cookies))
            for c in cs:
                if c == 'agent-login':
                    json_cookie = json.loads(
                        base64.b64decode(cs[c].value).decode('utf-8'))
                    key = json_cookie.get('public_key')
                    public_key = macaroonbakery.PublicKey.deserialize(key)
            ms = httpbakery.extract_macaroons(request.headers)
            if len(ms) == 0:
                b = macaroonbakery.Bakery(key=discharge_key)
                m = b.oven.macaroon(
                    version=macaroonbakery.LATEST_BAKERY_VERSION,
                    expiry=datetime.utcnow() + timedelta(days=1),
                    caveats=[macaroonbakery.local_third_party_caveat(
                        public_key,
                        version=httpbakery.request_version(request.headers))],
                    ops=[macaroonbakery.Op(entity='agent', action='login')])
                content, headers = httpbakery.discharge_required_response(
                    m, '/',
                    'test',
                    'message')
                resp = response(status_code=401,
                                content=content,
                                headers=headers)
                return request.hooks['response'][0](resp)

            return {
                'status_code': 200,
                'content': {
                    'agent-login': True
                }
            }

        @urlmatch(path='.*/wait?$')
        def wait(url, request):
            class EmptyChecker(macaroonbakery.ThirdPartyCaveatChecker):
                def check_third_party_caveat(self, ctx, info):
                    return []
            if InfoStorage.info is None:
                self.fail('visit url has not been visited')
            m = macaroonbakery.discharge(checkers.AuthContext(),
                                         InfoStorage.info.id,
                                         InfoStorage.info.caveat,
                                         discharge_key,
                                         EmptyChecker(), _DischargerLocator())
            return {
                'status_code': 200,
                'content': {
                    'Macaroon': m.to_dict()
                }
            }

        with HTTMock(server_get):
            with HTTMock(discharge):
                with HTTMock(visit):
                    with HTTMock(wait):
                        resp = requests.get(
                            'http://0.1.2.3/here',
                            auth=httpbakery.BakeryAuth(
                                interaction_methods=[
                                    httpbakery.AgentInteractor(
                                        httpbakery.AuthInfo(
                                            key=key,
                                            agents=[
                                                httpbakery.Agent(
                                                    username='test-user',
                                                    url=u'http://0.3.2.1'
                                                )
                                            ]))
                                    ]))
        self.assertEquals(resp.content, b'done')


agent_file = '''
{
  "key": {
    "public": "YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=",
    "private": "CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJEU="
    },
  "agents": [{
    "url": "https://1.example.com/",
    "username": "user-1"
    }, {
    "url": "https://2.example.com/discharger",
    "username": "user-2"
  }]
}
'''


bad_key_agent_file = '''
{
  "key": {
    "public": "YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=",
    "private": "CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJE=="
    },
  "agents": [{
    "url": "https://1.example.com/",
    "username": "user-1"
    }, {
    "url": "https://2.example.com/discharger",
    "username": "user-2"
  }]
}
'''


no_username_agent_file = '''
{
  "key": {
    "public": "YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=",
    "private": "CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJEU="
    },
  "agents": [{
    "url": "https://1.example.com/"
    }, {
    "url": "https://2.example.com/discharger",
    "username": "user-2"
  }]
}
'''
