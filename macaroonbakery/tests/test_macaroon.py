# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

from unittest import TestCase

import six

import nacl.utils

from macaroonbakery import bakery, macaroon, checkers, codec


class TestMacaroon(TestCase):
    def test_new_macaroon(self):
        m = macaroon.Macaroon(b'rootkey',
                              b'some id',
                              'here',
                              bakery.LATEST_BAKERY_VERSION)
        self.assertIsNotNone(m)
        self.assertEquals(m._macaroon.identifier, 'some id')
        self.assertEquals(m._macaroon.location, 'here')
        self.assertEquals(m.version, macaroon.macaroon_version(
            bakery.LATEST_BAKERY_VERSION))

    def test_add_first_party_caveat(self):
        m = macaroon.Macaroon('rootkey',
                              'some id',
                              'here',
                              bakery.LATEST_BAKERY_VERSION)
        m = m.add_caveat(checkers.Caveat('test_condition'))
        caveats = m.first_party_caveats()
        self.assertEquals(len(caveats), 1)
        self.assertEquals(caveats[0].caveat_id, 'test_condition')

    def test_add_third_party_caveat(self):
        m = macaroon.Macaroon('rootkey',
                              'some id',
                              'here',
                              bakery.LATEST_BAKERY_VERSION)
        loc = macaroon.ThirdPartyLocator()
        fp_key = nacl.public.PrivateKey.generate()
        tp_key = nacl.public.PrivateKey.generate()

        loc.add_info('test_location',
                     bakery.ThirdPartyInfo(
                         bakery.BAKERY_V1,
                         tp_key.public_key))
        m = m.add_caveat(checkers.Caveat(condition='test_condition',
                                         location='test_location'),
                         fp_key, loc)

        tp_cav = m.third_party_caveats()
        self.assertEquals(len(tp_cav), 1)
        self.assertEquals(tp_cav[0].location, 'test_location')
        cav = codec.decode_caveat(tp_key, six.b(tp_cav[0].caveat_id))
        self.assertEquals(cav, macaroon.ThirdPartyCaveatInfo(
            condition='test_condition',
            first_party_public_key=fp_key.public_key,
            third_party_key_pair=tp_key,
            root_key='random',
            caveat=six.b(tp_cav[0].caveat_id),
            version=bakery.BAKERY_V1,
            ns=macaroon.legacy_namespace()
        ))
