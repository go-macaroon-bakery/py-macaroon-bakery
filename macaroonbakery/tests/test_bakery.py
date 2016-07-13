# Copyright 2016 Canonical Ltd.
# Licensed under the AGPLv3, see LICENCE file for details.
import base64
import json

from unittest import TestCase
from mock import (
    patch,
)

from httmock import (
    HTTMock,
    urlmatch,
)

from macaroonbakery import bakery

ID_PATH = 'http://example.com/someprotecteurl'

json_macaroon = {
    u'identifier': u'macaroon-identifier',
    u'caveats': [
        {
            u'cl': u'http://example.com/identity/v1/discharger',
            u'vid': u'zgtQa88oS9UF45DlJniRaAUT4qqHhLxQzCeUU9N2O1Uu-'
                    u'yhFulgGbSA0zDGdkrq8YNQAxGiARA_-AGxyoh25kiTycb8u47pD',
            u'cid': u'eyJUaGlyZFBhcnR5UHV'
        }, {
            u'cid': u'allow read-no-terms write'
        }, {
            u'cid': u'time-before 2016-07-19T14:29:14.312669464Z'
        }],
    u'location': u'charmstore',
    u'signature': u'52d17cb11f5c84d58441bc0ffd7cc396'
                  u'5115374ce2fa473ecf06265b5d4d9e81'
}

discharge_token = [{
    u'identifier': u'token-identifier===',
    u'caveats': [{
        u'cid': u'declared username someone'
    }, {
        u'cid': u'time-before 2016-08-15T15:55:52.428319076Z'
    }, {
        u'cid': u'origin '
    }],
    u'location': u'https://example.com/identity',
    u'signature': u'5ae0e7a2abf806bdd92f510fcd3'
                  u'198f520691259abe76ffae5623dae048769ef'
}]

discharged_macaroon = {
    u'identifier': u'discharged-identifier=',
    u'caveats': [{
        u'cid': u'declared uuid a1130b10-3deb-59b7-baf0-c2a3f83e7382'
    }, {
        u'cid': u'declared username someone'
    }, {
        u'cid': u'time-before 2016-07-19T15:55:52.432439055Z'
    }],
    u'location': u'',
    u'signature': u'3513db5503ab17f9576760cd28'
                  u'ce658ce8bf6b43038255969fc3c1cd8b172345'
}


@urlmatch(path='.*/someprotecteurl')
def first_407_then_200(url, request):
    if request.headers.get('Macaroons') is None:
        return {
            'status_code': 407,
            'content': {
                'Info': {
                    'Macaroon': json_macaroon
                },
                'Message': 'verification failed: no macaroon '
                           'cookies in request',
                'Code': 'macaroon discharge required'
            }
        }
    else:
        return {
            'status_code': 200,
            'content': {
                'Value': 'some value'
            }
        }


@urlmatch(path='.*/someprotecteurl')
def valid_200(url, request):
    return {
        'status_code': 200,
        'content': {
            'Value': 'some value'
        }
    }


@urlmatch(path='.*/discharge')
def discharge_200(url, request):
    return {
        'status_code': 200,
        'content': {
            'Macaroon': discharged_macaroon
        }
    }


@urlmatch(path='.*/discharge')
def discharge_401(url, request):
    return {
        'status_code': 401,
        'content': {
            'Code': 'interaction required',
            'Info': {
                'VisitURL': 'http://example.com/visit',
                'WaitURL': 'http://example.com/wait'
            }
        }
    }


@urlmatch(path='.*/wait')
def wait_after_401(url, request):
    return {
        'status_code': 200,
        'content': {
            'DischargeToken': discharge_token,
            'Macaroon': discharged_macaroon
        }
    }


class TestBakery(TestCase):
    def setUp(self):
        self.bakery = bakery.Bakery()

    def test_407_then_200_on_discharge(self):
        with HTTMock(first_407_then_200):
            with HTTMock(discharge_200):
                data = self.bakery.get(ID_PATH)
        self.assertEquals({'Value': 'some value'}, json.loads(data.content))
        self.assertIsNotNone(self.bakery.macaroons,
                             'macaroons should have been set')
        decoded = base64.urlsafe_b64decode(self.bakery.macaroons)
        m = bakery.deserialize(json_macaroon)
        dm = m.prepare_for_request(
            bakery.deserialize(discharged_macaroon))
        json_dm = json.loads(base64.urlsafe_b64decode(dm.serialize_json()))
        self.assertEquals([json_macaroon, json_dm], json.loads(decoded))
        self.assertIsNone(self.bakery.discharge_token)

    def test_macaroon_valid_from_start(self):
        with HTTMock(valid_200):
            data = self.bakery.get(ID_PATH)
        self.assertEquals({'Value': 'some value'}, json.loads(data.content))

    @patch('webbrowser.open')
    def test_407_then_401_on_discharge(self, mock_open):
        with HTTMock(first_407_then_200):
            with HTTMock(discharge_401):
                with HTTMock(wait_after_401):
                    data = self.bakery.get(ID_PATH)
        self.assertEquals({'Value': 'some value'}, json.loads(data.content))
        self.assertIsNotNone(self.bakery.macaroons,
                             'macaroons should have been set')
        decoded = base64.urlsafe_b64decode(self.bakery.macaroons)
        m = bakery.deserialize(json_macaroon)
        dm = m.prepare_for_request(
            bakery.deserialize(discharged_macaroon))
        json_dm = json.loads(base64.urlsafe_b64decode(dm.serialize_json()))
        self.assertEquals([json_macaroon, json_dm], json.loads(decoded))
        self.assertEquals(bakery.to_base64(discharge_token),
                          self.bakery.discharge_token)
