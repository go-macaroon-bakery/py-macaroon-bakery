# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
from collections import namedtuple
import json
import requests
from macaroonbakery import utils

import nacl.utils
from nacl.public import Box

from pymacaroons import Macaroon

ERR_INTERACTION_REQUIRED = 'interaction required'
ERR_DISCHARGE_REQUIRED = 'macaroon discharge required'
TIME_OUT = 30
DEFAULT_PROTOCOL_VERSION = {'Bakery-Protocol-Version': '1'}
MAX_DISCHARGE_RETRIES = 3

BAKERY_V0 = 0
BAKERY_V1 = 1
BAKERY_V2 = 2
BAKERY_V3 = 3
LATEST_BAKERY_VERSION = BAKERY_V3
NONCE_LEN = 24


# A named tuple composed of the visit_url and wait_url coming from the error
# response in discharge
_Info = namedtuple('Info', 'visit_url wait_url')


class DischargeException(Exception):
    '''A discharge error occurred.'''


def discharge_all(macaroon, visit_page=None, jar=None, key=None):
    '''Gathers discharge macaroons for all the third party caveats in macaroon.

    All the discharge macaroons will be bound to the primary macaroon.
    The key parameter may optionally hold the key of the client, in which case
    it will be used to discharge any third party caveats with the special
    location "local". In this case, the caveat itself must be "true". This
    can be used by a server to ask a client to prove ownership of the
    private key.
    @param macaroon The macaroon to be discharged.
    @param visit_page function called when the discharge process requires
    further interaction.
    @param jar the storage for the cookies.
    @param key optional nacl key.
    @return An array with macaroon as the first element, followed by all the
    discharge macaroons.
    '''
    discharges = [macaroon]
    if visit_page is None:
        visit_page = utils.visit_page_with_browser
    if jar is None:
        jar = requests.cookies.RequestsCookieJar()
    client = _Client(visit_page, jar)
    try:
        client.discharge_caveats(macaroon, discharges, macaroon, key)
    except Exception as exc:
        raise DischargeException('unable to discharge the macaroon', exc)
    return discharges


def discharge(key, id, caveat=None, checker=None, locator=None):
    '''Creates a macaroon to discharge a third party caveat.

    @param key nacl key holds the key to use to decrypt the third party
    caveat information and to encrypt any additional
    third party caveats returned by the caveat checker
    @param id bytes holding the id to give to the discharge macaroon.
    If caveat is empty, then the id also holds the encrypted third party caveat
    @param caveat bytes holding the encrypted third party caveat.
    If this is None, id will be used
    @param checker used to check the third party caveat,
    and may also return further caveats to be added to
    the discharge macaroon. object that will have a function
    check_third_party_caveat taking a dict of third party caveat info
    as parameter.
    @param locator used to retrieve information on third parties
    referred to by third party caveats returned by the checker. Object that
    will have a third_party_info function taking a location as a string.
    @return macaroon with third party caveat discharged.
    '''
    if caveat is None:
        caveat = id
    cav_info = _decode_caveat(key, caveat)
    return Macaroon(location='', key=cav_info['RootKey'], identifier=id)


class _Client:
    def __init__(self, visit_page, jar):
        self._visit_page = visit_page
        self._jar = jar

    def discharge_caveats(self, macaroon, discharges,
                          primary_macaroon, key):
        '''Gathers discharge macaroons for all the third party caveats.

        @param macaroon the macaroon to discharge.
        @param discharges the list of discharged macaroons.
        @param primary_macaroon used for the signature of the discharge
        macaroon.
        @param key nacl key holds the key to use to decrypt the third party
        caveat information and to encrypt any additional
        third party caveats returned by the caveat checker
        '''
        caveats = macaroon.third_party_caveats()
        for caveat in caveats:
            location = caveat.location
            b_cav_id = caveat.caveat_id.encode('utf-8')
            if key is not None and location == 'local':
                # if tuple is only 2 element otherwise TODO add caveat
                dm = discharge(key, id=b_cav_id)
            else:
                dm = self._get_discharge(location, b_cav_id)
            dm = primary_macaroon.prepare_for_request(dm)
            discharges.append(dm)
            self.discharge_caveats(dm, discharges, primary_macaroon, key)

    def _get_discharge(self, third_party_location,
                       third_party_caveat_condition):
        '''Get the discharge macaroon from the third party location.

        @param third_party_location where to get a discharge from.
        @param third_party_caveat_condition encoded 64 string associated to the
        discharged macaroon.
        @return a discharge macaroon.
        @raise DischargeError when an error occurs during the discharge
            process.
        '''
        headers = DEFAULT_PROTOCOL_VERSION
        payload = {'id': third_party_caveat_condition}

        response = requests.post(third_party_location + '/discharge',
                                 headers=headers,
                                 data=payload,
                                 # timeout=TIME_OUT, TODO: add a time out
                                 cookies=self._jar)
        status_code = response.status_code
        if status_code == 200:
            return _extract_macaroon_from_response(response)
        if (status_code == 401 and
                response.headers.get('WWW-Authenticate') == 'Macaroon'):
            error = response.json()
            if error.get('Code', '') != ERR_INTERACTION_REQUIRED:
                return DischargeException('unable to get code from discharge')
            info = _extract_urls(response)
            self._visit_page(info.visit_url)
            # Wait on the wait url and then get a macaroon if validated.
            return _acquire_macaroon_from_wait(info.wait_url)


def _decode_caveat(key, caveat):
    '''Attempts to decode caveat by decrypting the encrypted part using key.

    @param key a nacl key.
    @param caveat bytes to be decoded.
    @return a dict of third party caveat info.
    '''
    data = base64.b64decode(caveat).decode('utf-8')
    tpid = json.loads(data)
    third_party_public_key = nacl.public.PublicKey(
        base64.b64decode(tpid['ThirdPartyPublicKey']))
    if key.public_key != third_party_public_key:
        return 'some error'
    if tpid.get('FirstPartyPublicKey', None) is None:
        return 'target service public key not specified'
    # The encrypted string is base64 encoded in the JSON representation.
    secret = base64.b64decode(tpid['Id'])
    first_party_public_key = nacl.public.PublicKey(
        base64.b64decode(tpid['FirstPartyPublicKey']))
    box = Box(key,
              first_party_public_key)
    c = box.decrypt(secret, base64.b64decode(tpid['Nonce']))
    record = json.loads(c.decode('utf-8'))
    return {
        'Condition': record['Condition'],
        'FirstPartyPublicKey': first_party_public_key,
        'ThirdPartyKeyPair': key,
        'RootKey': base64.b64decode(record['RootKey']),
        'Caveat': caveat,
        'MacaroonId': id,
    }


def _extract_macaroon_from_response(response):
    '''Extract the macaroon from a direct successful discharge.

    @param response from direct successful discharge.
    @return a macaroon object.
    @raises DischargeError if any error happens.
    '''
    response_json = response.json()
    return utils.deserialize(response_json['Macaroon'])


def _acquire_macaroon_from_wait(wait_url):
    ''' Return the macaroon acquired from the wait endpoint.

    Note that will block until the user interaction has completed.

    @param wait_url the get url to call to get a macaroon.
    @return a macaroon object
    @raises DischargeError if any error happens.
    '''
    resp = requests.get(wait_url, headers=DEFAULT_PROTOCOL_VERSION)
    response_json = resp.json()
    macaroon = response_json['Macaroon']
    return utils.deserialize(macaroon)


def _extract_urls(response):
    '''Return _Info of the visit and wait URL from response.

    @param response the response from the discharge endpoint.
    @return a _Info object of the visit and wait URL.
    @raises DischargeError for ant error during the process response.
    '''
    response_json = response.json()
    visit_url = response_json['Info']['VisitURL']
    wait_url = response_json['Info']['WaitURL']
    return _Info(visit_url=visit_url, wait_url=wait_url)


class ThirdPartyInfo:
    def __init__(self, version, public_key):
        '''
        @param version holds latest the bakery protocol version supported
        by the discharger.
        @param public_key holds the public nacl key of the third party.
        '''
        self.version = version
        self.public_key = public_key
