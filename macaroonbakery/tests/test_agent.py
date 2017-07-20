# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
import json
import os
import tempfile
from unittest import TestCase

import nacl.encoding
import requests.cookies
import six

import macaroonbakery.httpbakery.agent as agent


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
        cookies, key = agent.load_agent_file(self.agent_filename)
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
        c1, key = agent.load_agent_file(self.agent_filename, cookies=cookies)
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
        with self.assertRaises(agent.AgentFileFormatError):
            agent.load_agent_file(self.bad_key_agent_filename)

    def test_load_agents_with_no_username(self):
        with self.assertRaises(agent.AgentFileFormatError):
            agent.load_agent_file(self.no_username_agent_filename)


agent_file = """
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
"""


bad_key_agent_file = """
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
"""


no_username_agent_file = """
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
"""
