# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import base64
from unittest import TestCase

import nacl.public
import six

import macaroonbakery
from macaroonbakery import utils
from macaroonbakery import codec
import macaroonbakery.checkers as checkers


class TestCodec(TestCase):
    def setUp(self):
        self.fp_key = macaroonbakery.generate_key()
        self.tp_key = macaroonbakery.generate_key()

    def test_v1_round_trip(self):
        tp_info = macaroonbakery.ThirdPartyInfo(
            version=macaroonbakery.BAKERY_V1,
            public_key=self.tp_key.public_key)
        cid = macaroonbakery.encode_caveat(
            'is-authenticated-user',
            b'a random string',
            tp_info,
            self.fp_key,
            None)
        res = macaroonbakery.decode_caveat(self.tp_key, cid)
        self.assertEquals(res, macaroonbakery.ThirdPartyCaveatInfo(
            first_party_public_key=self.fp_key.public_key,
            root_key=b'a random string',
            condition='is-authenticated-user',
            caveat=cid,
            third_party_key_pair=self.tp_key,
            version=macaroonbakery.BAKERY_V1,
            id=None,
            namespace=macaroonbakery.legacy_namespace()
        ))

    def test_v2_round_trip(self):
        tp_info = macaroonbakery.ThirdPartyInfo(
            version=macaroonbakery.BAKERY_V2,
            public_key=self.tp_key.public_key)
        cid = macaroonbakery.encode_caveat(
            'is-authenticated-user',
            b'a random string',
            tp_info,
            self.fp_key,
            None)
        res = macaroonbakery.decode_caveat(self.tp_key, cid)
        self.assertEquals(res, macaroonbakery.ThirdPartyCaveatInfo(
            first_party_public_key=self.fp_key.public_key,
            root_key=b'a random string',
            condition='is-authenticated-user',
            caveat=cid,
            third_party_key_pair=self.tp_key,
            version=macaroonbakery.BAKERY_V2,
            id=None,
            namespace=macaroonbakery.legacy_namespace()
        ))

    def test_v3_round_trip(self):
        tp_info = macaroonbakery.ThirdPartyInfo(
            version=macaroonbakery.BAKERY_V3,
            public_key=self.tp_key.public_key)
        ns = checkers.Namespace()
        ns.register('testns', 'x')
        cid = macaroonbakery.encode_caveat(
            'is-authenticated-user',
            b'a random string',
            tp_info,
            self.fp_key,
            ns)
        res = macaroonbakery.decode_caveat(self.tp_key, cid)
        self.assertEquals(res, macaroonbakery.ThirdPartyCaveatInfo(
            first_party_public_key=self.fp_key.public_key,
            root_key=b'a random string',
            condition='is-authenticated-user',
            caveat=cid,
            third_party_key_pair=self.tp_key,
            version=macaroonbakery.BAKERY_V3,
            id=None,
            namespace=ns
        ))

    def test_empty_caveat_id(self):
        with self.assertRaises(macaroonbakery.VerificationError) as context:
            macaroonbakery.decode_caveat(self.tp_key, b'')
        self.assertTrue('empty third party caveat' in str(context.exception))

    def test_decode_caveat_v1_from_go(self):
        tp_key = macaroonbakery.PrivateKey(
            nacl.public.PrivateKey(base64.b64decode(
                'TSpvLpQkRj+T3JXnsW2n43n5zP/0X4zn0RvDiWC3IJ0=')))
        fp_key = macaroonbakery.PrivateKey(
            nacl.public.PrivateKey(base64.b64decode(
                'KXpsoJ9ujZYi/O2Cca6kaWh65MSawzy79LWkrjOfzcs=')))
        root_key = base64.b64decode('vDxEmWZEkgiNEFlJ+8ruXe3qDSLf1H+o')
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
        cav = macaroonbakery.decode_caveat(tp_key, encrypted_cav)
        self.assertEquals(cav, macaroonbakery.ThirdPartyCaveatInfo(
            condition='caveat condition',
            first_party_public_key=fp_key.public_key,
            third_party_key_pair=tp_key,
            root_key=root_key,
            caveat=encrypted_cav,
            version=macaroonbakery.BAKERY_V1,
            id=None,
            namespace=macaroonbakery.legacy_namespace()
        ))

    def test_decode_caveat_v2_from_go(self):
        tp_key = macaroonbakery.PrivateKey(nacl.public.PrivateKey(
            base64.b64decode(
                'TSpvLpQkRj+T3JXnsW2n43n5zP/0X4zn0RvDiWC3IJ0=')))
        fp_key = macaroonbakery.PrivateKey(
            nacl.public.PrivateKey(base64.b64decode(
                'KXpsoJ9ujZYi/O2Cca6kaWh65MSawzy79LWkrjOfzcs=')))
        root_key = base64.b64decode('wh0HSM65wWHOIxoGjgJJOFvQKn2jJFhC')
        # This caveat has been generated from the go code
        # to check the compatibilty
        encrypted_cav = base64.urlsafe_b64decode(
            utils.add_base64_padding(six.b(
                'AvD-xlUf2MdGMgtu7OKRQnCP1OQJk6PKeFWRK26WIBA6DNwKGIHq9xGcHS9IZ'
                'Lh0cL6D9qpeKI0mXmCPfnwRQDuVYC8y5gVWd-oCGZaj5TGtk3byp2Vnw6ojmt'
                'sULDhY59YA_J_Y0ATkERO5T9ajoRWBxU2OXBoX6bImXA')))
        cav = macaroonbakery.decode_caveat(tp_key, encrypted_cav)
        self.assertEqual(cav, macaroonbakery.ThirdPartyCaveatInfo(
            condition='third party condition',
            first_party_public_key=fp_key.public_key,
            third_party_key_pair=tp_key,
            root_key=root_key,
            caveat=encrypted_cav,
            version=macaroonbakery.BAKERY_V2,
            id=None,
            namespace=macaroonbakery.legacy_namespace()
        ))

    def test_decode_caveat_v3_from_go(self):
        tp_key = macaroonbakery.PrivateKey(
            nacl.public.PrivateKey(base64.b64decode(
                'TSpvLpQkRj+T3JXnsW2n43n5zP/0X4zn0RvDiWC3IJ0=')))
        fp_key = macaroonbakery.PrivateKey(nacl.public.PrivateKey(
            base64.b64decode(
                'KXpsoJ9ujZYi/O2Cca6kaWh65MSawzy79LWkrjOfzcs=')))
        root_key = base64.b64decode(b'oqOXI3/Mz/pKjCuFOt2eYxb7ndLq66GY')
        # This caveat has been generated from the go code
        # to check the compatibilty
        encrypted_cav = base64.urlsafe_b64decode(
            utils.add_base64_padding(six.b(
                'A_D-xlUf2MdGMgtu7OKRQnCP1OQJk6PKeFWRK26WIBA6DNwKGNLeFSkD2M-8A'
                'EYvmgVH95GWu7T7caKxKhhOQFcEKgnXKJvYXxz1zin4cZc4Q6C7gVqA-J4_j3'
                '1LX4VKxymqG62UGPo78wOv0_fKjr3OI6PPJOYOQgBMclemlRF2')))
        cav = macaroonbakery.decode_caveat(tp_key, encrypted_cav)
        self.assertEquals(cav, macaroonbakery.ThirdPartyCaveatInfo(
            condition='third party condition',
            first_party_public_key=fp_key.public_key,
            third_party_key_pair=tp_key,
            root_key=root_key,
            caveat=encrypted_cav,
            version=macaroonbakery.BAKERY_V3,
            id=None,
            namespace=macaroonbakery.legacy_namespace()
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
            macaroonbakery.encode_uvarint(test[0], data)
            for v in test[1]:
                expected.append(v)
            self.assertEquals(data, expected)
            val = codec.decode_uvarint(bytes(data))
            self.assertEquals(test[0], val[0])
            self.assertEquals(len(test[1]), val[1])
