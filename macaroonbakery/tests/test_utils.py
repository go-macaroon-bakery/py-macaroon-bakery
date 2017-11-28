from unittest import TestCase
from datetime import datetime

import pytz

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
