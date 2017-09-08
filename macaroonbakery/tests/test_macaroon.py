# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

from unittest import TestCase

import nacl.utils

from macaroonbakery import LATEST_BAKERY_VERSION, BAKERY_V1, macaroon, codec
from macaroonbakery.bakery import ThirdPartyInfo
from macaroonbakery.macaroon import ThirdPartyLocator
from macaroonbakery.third_party import legacy_namespace, ThirdPartyCaveatInfo
from macaroonbakery import checkers


class TestMacaroon(TestCase):
    def test_new_macaroon(self):
        m = macaroon.Macaroon(b'rootkey',
                              b'some id',
                              'here',
                              LATEST_BAKERY_VERSION)
        self.assertIsNotNone(m)
        self.assertEquals(m._macaroon.identifier, b'some id')
        self.assertEquals(m._macaroon.location, 'here')
        self.assertEquals(m.version(), LATEST_BAKERY_VERSION)

    def test_add_first_party_caveat(self):
        m = macaroon.Macaroon('rootkey',
                              'some id',
                              'here',
                              LATEST_BAKERY_VERSION)
        m.add_caveat(checkers.Caveat('test_condition'))
        caveats = m.first_party_caveats()
        self.assertEquals(len(caveats), 1)
        self.assertEquals(caveats[0].caveat_id, b'test_condition')

    def test_add_third_party_caveat(self):
        m = macaroon.Macaroon('rootkey',
                              'some id',
                              'here',
                              LATEST_BAKERY_VERSION)
        loc = ThirdPartyLocator()
        fp_key = nacl.public.PrivateKey.generate()
        tp_key = nacl.public.PrivateKey.generate()

        loc.add_info('test_location',
                     ThirdPartyInfo(
                         version=BAKERY_V1,
                         public_key=tp_key.public_key))
        m.add_caveat(checkers.Caveat(condition='test_condition',
                                     location='test_location'), fp_key, loc)

        tp_cav = m.third_party_caveats()
        self.assertEquals(len(tp_cav), 1)
        self.assertEquals(tp_cav[0].location, 'test_location')
        cav = codec.decode_caveat(tp_key, tp_cav[0].caveat_id)
        self.assertEquals(cav, ThirdPartyCaveatInfo(
            condition='test_condition',
            first_party_public_key=fp_key.public_key,
            third_party_key_pair=tp_key,
            root_key='random',
            caveat=tp_cav[0].caveat_id,
            version=BAKERY_V1,
            ns=legacy_namespace()
        ))
