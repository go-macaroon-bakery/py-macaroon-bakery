# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from unittest import TestCase

import nacl.utils

from macaroonbakery import bakery, codec, macaroon


class TestCodec(TestCase):
    def setUp(self):
        self.fp_key = nacl.public.PrivateKey.generate()
        self.tp_key = nacl.public.PrivateKey.generate()

    def test_v1_round_trip(self):
        tp_info = bakery.ThirdPartyInfo(bakery.BAKERY_V1,
                                        self.tp_key.public_key)
        cid = codec.encode_caveat('is-authenticated-user',
                                  b'a random string',
                                  tp_info,
                                  self.fp_key,
                                  None)

        res = codec.decode_caveat(self.tp_key, cid)
        self.assertEquals(res, macaroon.ThirdPartyCaveatInfo(
            first_party_public_key=self.fp_key.public_key,
            root_key='a random string',
            condition='is-authenticated-user',
            caveat=cid,
            third_party_key_pair=self.tp_key,
            version=bakery.BAKERY_V1))

    def test_empty_caveat_id(self):
        with self.assertRaises(ValueError) as context:
            codec.decode_caveat(self.tp_key, b'')
        self.assertTrue('empty third party caveat' in str(context.exception))
