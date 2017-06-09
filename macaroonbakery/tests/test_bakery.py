# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from unittest import TestCase

import requests

from mock import (
    patch,
)

from httmock import (
    HTTMock,
    urlmatch,
    response
)

from macaroonbakery import httpbakery

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
    if request.headers.get('cookie', '').startswith('macaroon-'):
        return {
            'status_code': 200,
            'content': {
                'Value': 'some value'
            }
        }
    else:
        resp = response(status_code=407,
                        content={
                            'Info': {
                                'Macaroon': json_macaroon,
                                'MacaroonPath': '/',
                                'CookieNameSuffix': 'test'
                            },
                            'Message': 'verification failed: no macaroon '
                                       'cookies in request',
                            'Code': 'macaroon discharge required'
                        },
                        headers={'Content-Type': 'application/json'})
        return request.hooks['response'][0](resp)


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
        },
        'headers': {
            'WWW-Authenticate': 'Macaroon'
        }
    }


@urlmatch(path='.*/wait')
def wait_after_401(url, request):
    if request.url != 'http://example.com/wait':
        return {'status_code': 500}

    return {
        'status_code': 200,
        'content': {
            'DischargeToken': discharge_token,
            'Macaroon': discharged_macaroon
        }
    }


class TestBakery(TestCase):
    def test_discharge(self):
        jar = requests.cookies.RequestsCookieJar()
        with HTTMock(first_407_then_200):
            with HTTMock(discharge_200):
                resp = requests.get(ID_PATH,
                                    cookies=jar,
                                    auth=httpbakery.BakeryAuth(cookies=jar))
        resp.raise_for_status()
        assert 'macaroon-test' in jar.keys()

    @patch('webbrowser.open')
    def test_407_then_401_on_discharge(self, mock_open):
        jar = requests.cookies.RequestsCookieJar()
        with HTTMock(first_407_then_200):
            with HTTMock(discharge_401):
                with HTTMock(wait_after_401):
                    resp = requests.get(ID_PATH,
                                        auth=httpbakery.BakeryAuth(
                                            cookies=jar))
                    resp.raise_for_status()
        mock_open.assert_called_once_with(u'http://example.com/visit', new=1)
        assert 'macaroon-test' in jar.keys()
