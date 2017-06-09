# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from unittest import TestCase

import base64
import six

import nacl.utils
from nacl.public import PrivateKey
from nacl.encoding import Base64Encoder

from macaroonbakery import bakery, codec, macaroon, namespace, utils


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
            root_key=b'a random string',
            condition='is-authenticated-user',
            caveat=cid,
            third_party_key_pair=self.tp_key,
            version=bakery.BAKERY_V1,
            ns=macaroon.legacy_namespace()
        ))

    def test_v2_round_trip(self):
        tp_info = bakery.ThirdPartyInfo(bakery.BAKERY_V2,
                                        self.tp_key.public_key)
        cid = codec.encode_caveat('is-authenticated-user',
                                  b'a random string',
                                  tp_info,
                                  self.fp_key,
                                  None)
        res = codec.decode_caveat(self.tp_key, cid)
        self.assertEquals(res, macaroon.ThirdPartyCaveatInfo(
            first_party_public_key=self.fp_key.public_key,
            root_key=b'a random string',
            condition='is-authenticated-user',
            caveat=cid,
            third_party_key_pair=self.tp_key,
            version=bakery.BAKERY_V2,
            ns=macaroon.legacy_namespace()
        ))

    def test_v3_round_trip(self):
        tp_info = bakery.ThirdPartyInfo(bakery.BAKERY_V3,
                                        self.tp_key.public_key)
        ns = namespace.Namespace()
        ns.register('testns', 'x')
        cid = codec.encode_caveat('is-authenticated-user',
                                  b'a random string',
                                  tp_info,
                                  self.fp_key,
                                  ns)
        res = codec.decode_caveat(self.tp_key, cid)
        self.assertEquals(res, macaroon.ThirdPartyCaveatInfo(
            first_party_public_key=self.fp_key.public_key,
            root_key=b'a random string',
            condition='is-authenticated-user',
            caveat=cid,
            third_party_key_pair=self.tp_key,
            version=bakery.BAKERY_V3,
            ns=ns
        ))

    def test_empty_caveat_id(self):
        with self.assertRaises(ValueError) as context:
            codec.decode_caveat(self.tp_key, b'')
        self.assertTrue('empty third party caveat' in str(context.exception))

    def test_decode_caveat_v1_from_go(self):
        tp_key = PrivateKey(base64.b64decode(
            'TSpvLpQkRj+T3JXnsW2n43n5zP/0X4zn0RvDiWC3IJ0='))
        fp_key = PrivateKey(base64.b64decode(
            'KXpsoJ9ujZYi/O2Cca6kaWh65MSawzy79LWkrjOfzcs='))
        fp_key.encode(Base64Encoder)
        # This caveat has been generated from the go code
        # to check the compatibilty
        encrypted_cav = six.b(
            'eyJUaGlyZFBhcnR5UHVibGljS2V5IjoiOFA3R1ZZc3BlWlN4c'
            '3hFdmJsSVFFSTFqdTBTSWl0WlIrRFdhWE40cmxocz0iLCJGaX'
            'JzdFBhcnR5UHVibGljS2V5IjoiSDlqSFJqSUxidXppa1VKd2o'
            '5VGtDWk9qeW5oVmtTdHVsaUFRT2d6Y0NoZz0iLCJOb25jZSI6'
            'Ii9lWTRTTWR6TGFxbDlsRFc3bHUyZTZuSzJnVG9veVl0IiwiS'
            'WQiOiJra0ZuOGJEaEt4RUxtUjd0NkJxTU0vdHhMMFVqaEZjR1'
            'BORldUUExGdjVla1dWUjA4Uk1sbGJhc3c4VGdFbkhzM0laeVo'
            '0V2lEOHhRUWdjU3ljOHY4eUt4dEhxejVEczJOYmh1ZDJhUFdt'
            'UTVMcVlNWitmZ2FNaTAxdE9DIn0=')
        cav = codec.decode_caveat(tp_key, encrypted_cav)
        self.assertEquals(cav, macaroon.ThirdPartyCaveatInfo(
            condition='caveat condition',
            first_party_public_key=fp_key.public_key,
            third_party_key_pair=tp_key,
            root_key=b'random',
            caveat=encrypted_cav,
            version=bakery.BAKERY_V1,
            ns=macaroon.legacy_namespace()
        ))

    def test_decode_caveat_v2_from_go(self):
        tp_key = PrivateKey(base64.b64decode(
            'TSpvLpQkRj+T3JXnsW2n43n5zP/0X4zn0RvDiWC3IJ0='))
        fp_key = PrivateKey(base64.b64decode(
            'KXpsoJ9ujZYi/O2Cca6kaWh65MSawzy79LWkrjOfzcs='))
        # This caveat has been generated from the go code
        # to check the compatibilty
        encrypted_cav = base64.urlsafe_b64decode(
            utils.add_base64_padding(six.b(
                'AvD-xlUf2MdGMgtu7OKRQnCP1OQJk6PKeFWRK26WIBA6DNwKGIHq9xGcHS9IZ'
                'Lh0cL6D9qpeKI0mXmCPfnwRQDuVYC8y5gVWd-oCGZaj5TGtk3byp2Vnw6ojmt'
                'sULDhY59YA_J_Y0ATkERO5T9ajoRWBxU2OXBoX6bImXA')))
        cav = codec.decode_caveat(tp_key, encrypted_cav)
        self.assertEquals(cav, macaroon.ThirdPartyCaveatInfo(
            condition='third party condition',
            first_party_public_key=fp_key.public_key,
            third_party_key_pair=tp_key,
            root_key=b'random',
            caveat=encrypted_cav,
            version=bakery.BAKERY_V2,
            ns=macaroon.legacy_namespace()
        ))

    def test_decode_caveat_v3_from_go(self):
        tp_key = PrivateKey(base64.b64decode(
            'TSpvLpQkRj+T3JXnsW2n43n5zP/0X4zn0RvDiWC3IJ0='))
        fp_key = PrivateKey(base64.b64decode(
            'KXpsoJ9ujZYi/O2Cca6kaWh65MSawzy79LWkrjOfzcs='))
        # This caveat has been generated from the go code
        # to check the compatibilty
        encrypted_cav = base64.urlsafe_b64decode(
            utils.add_base64_padding(six.b(
                'A_D-xlUf2MdGMgtu7OKRQnCP1OQJk6PKeFWRK26WIBA6DNwKGNLeFSkD2M-8A'
                'EYvmgVH95GWu7T7caKxKhhOQFcEKgnXKJvYXxz1zin4cZc4Q6C7gVqA-J4_j3'
                '1LX4VKxymqG62UGPo78wOv0_fKjr3OI6PPJOYOQgBMclemlRF2')))
        cav = codec.decode_caveat(tp_key, encrypted_cav)
        self.assertEquals(cav, macaroon.ThirdPartyCaveatInfo(
            condition='third party condition',
            first_party_public_key=fp_key.public_key,
            third_party_key_pair=tp_key,
            root_key=b'random',
            caveat=encrypted_cav,
            version=bakery.BAKERY_V3,
            ns=macaroon.legacy_namespace()
        ))

    def test_encode_decode_varint(self):
        tests = [
            (12, [12]),
            (127, [127]),
            (128, [128, 1]),
            (129, [129, 1]),
            (1234567, [135, 173, 75]),
            (12131231231312, [208, 218, 233, 173, 136, 225, 2])
        ]
        for test in tests:
            data = bytearray()
            expected = bytearray()
            codec._encode_uvarint(test[0], data)
            for v in test[1]:
                expected.append(v)
            self.assertEquals(data, expected)
            val = codec._decode_uvarint(bytes(data))
            self.assertEquals(test[0], val[0])
            self.assertEquals(len(test[1]), val[1])
