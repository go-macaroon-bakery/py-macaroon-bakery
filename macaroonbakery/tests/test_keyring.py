# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import unittest

from httmock import urlmatch, HTTMock

import macaroonbakery
from macaroonbakery import httpbakery


class TestKeyRing(unittest.TestCase):

    def test_cache_fetch(self):
        key = macaroonbakery.generate_key()

        @urlmatch(path='.*/discharge/info')
        def discharge_info(url, request):
            return {
                'status_code': 200,
                'content': {
                    'Version': macaroonbakery.LATEST_BAKERY_VERSION,
                    'PublicKey': key.public_key.encode().decode('utf-8')
                }
            }

        expectInfo = macaroonbakery.ThirdPartyInfo(
            public_key=key.public_key,
            version=macaroonbakery.LATEST_BAKERY_VERSION
        )
        kr = httpbakery.ThirdPartyLocator(allow_insecure=True)
        with HTTMock(discharge_info):
            info = kr.third_party_info('http://0.1.2.3/')
        self.assertEqual(info, expectInfo)

    def test_cache_norefetch(self):
        key = macaroonbakery.generate_key()

        @urlmatch(path='.*/discharge/info')
        def discharge_info(url, request):
            return {
                'status_code': 200,
                'content': {
                    'Version': macaroonbakery.LATEST_BAKERY_VERSION,
                    'PublicKey': key.public_key.encode().decode('utf-8')
                }
            }

        expectInfo = macaroonbakery.ThirdPartyInfo(
            public_key=key.public_key,
            version=macaroonbakery.LATEST_BAKERY_VERSION
        )
        kr = httpbakery.ThirdPartyLocator(allow_insecure=True)
        with HTTMock(discharge_info):
            info = kr.third_party_info('http://0.1.2.3/')
        self.assertEqual(info, expectInfo)
        info = kr.third_party_info('http://0.1.2.3/')
        self.assertEqual(info, expectInfo)

    def test_cache_fetch_no_version(self):
        key = macaroonbakery.generate_key()

        @urlmatch(path='.*/discharge/info')
        def discharge_info(url, request):
            return {
                'status_code': 200,
                'content': {
                    'PublicKey': key.public_key.encode().decode('utf-8')
                }
            }

        expectInfo = macaroonbakery.ThirdPartyInfo(
            public_key=key.public_key,
            version=macaroonbakery.BAKERY_V1
        )
        kr = httpbakery.ThirdPartyLocator(allow_insecure=True)
        with HTTMock(discharge_info):
            info = kr.third_party_info('http://0.1.2.3/')
        self.assertEqual(info, expectInfo)

    def test_allow_insecure(self):
        kr = httpbakery.ThirdPartyLocator()
        with self.assertRaises(macaroonbakery.error.ThirdPartyInfoNotFound):
            kr.third_party_info('http://0.1.2.3/')

    def test_fallback(self):
        key = macaroonbakery.generate_key()

        @urlmatch(path='.*/discharge/info')
        def discharge_info(url, request):
            return {
                'status_code': 404,
            }

        @urlmatch(path='.*/publickey')
        def public_key(url, request):
            return {
                'status_code': 200,
                'content': {
                    'PublicKey': key.public_key.encode().decode('utf-8')
                }
            }

        expectInfo = macaroonbakery.ThirdPartyInfo(
            public_key=key.public_key,
            version=macaroonbakery.BAKERY_V1
        )
        kr = httpbakery.ThirdPartyLocator(allow_insecure=True)
        with HTTMock(discharge_info):
            with HTTMock(public_key):
                info = kr.third_party_info('http://0.1.2.3/')
        self.assertEqual(info, expectInfo)
