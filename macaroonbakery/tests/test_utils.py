# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

from unittest import TestCase
from datetime import datetime
import pytz

import macaroonbakery as bakery
from macaroonbakery.utils import cookie


class CookieTest(TestCase):

    def test_cookie_expires_naive(self):
        timestamp = datetime.utcnow()
        c = cookie('http://example.com', 'test', 'value', expires=timestamp)
        self.assertEqual(
            c.expires, int((timestamp - datetime(1970, 1, 1)).total_seconds()))

    def test_cookie_expires_with_timezone(self):
        timestamp = datetime.now(pytz.UTC)
        self.assertRaises(
            ValueError, cookie, 'http://example.com', 'test', 'value',
            expires=timestamp)


class TestB64Decode(TestCase):
    def test_decode(self):
        test_cases = [{
            'about': 'empty string',
            'input': '',
            'expect': '',
        }, {
            'about': 'standard encoding, padded',
            'input': 'Z29+IQ==',
            'expect': 'go~!',
        }, {
            'about': 'URL encoding, padded',
            'input': 'Z29-IQ==',
            'expect': 'go~!',
        }, {
            'about': 'standard encoding, not padded',
            'input': 'Z29+IQ',
            'expect': 'go~!',
        }, {
            'about': 'URL encoding, not padded',
            'input': 'Z29-IQ',
            'expect': 'go~!',
        }, {
            'about': 'standard encoding, not enough much padding',
            'input': 'Z29+IQ=',
            'expect_error': 'illegal base64 data at input byte 8',
        }]
        for test in test_cases:
            if test.get('expect_error'):
                with self.assertRaises(ValueError, msg=test['about']) as e:
                    bakery.b64decode(test['input'])
                self.assertEqual(str(e.exception), 'Incorrect padding')
            else:
                self.assertEqual(bakery.b64decode(test['input']), test['expect'].encode('utf-8'), msg=test['about'])
