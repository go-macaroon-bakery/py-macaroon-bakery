# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from collections import namedtuple
import requests

from macaroonbakery import utils
from macaroonbakery.discharge import discharge
from macaroonbakery.checkers import checkers
from macaroonbakery.oven import Oven
from macaroonbakery.checker import Checker


ERR_INTERACTION_REQUIRED = 'interaction required'
ERR_DISCHARGE_REQUIRED = 'macaroon discharge required'
TIME_OUT = 30
DEFAULT_PROTOCOL_VERSION = {'Bakery-Protocol-Version': '1'}
MAX_DISCHARGE_RETRIES = 3

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
            b_cav_id = caveat.caveat_id
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


class Bakery(object):
    '''Convenience class that contains both an Oven and a Checker.
    '''
    def __init__(self, location=None, locator=None, ops_store=None, key=None,
                 identity_client=None, checker=None, root_key_store=None,
                 authorizer=None):
        '''Returns a new Bakery instance which combines an Oven with a
        Checker for the convenience of callers that wish to use both
        together.
        :param: checker holds the checker used to check first party caveats.
        If this is None, it will use checkers.Checker(None).
        :param: root_key_store holds the root key store to use.
        If you need to use a different root key store for different operations,
        you'll need to pass a root_key_store_for_ops value to Oven directly.
        :param: root_key_store If this is None, it will use MemoryKeyStore().
        Note that that is almost certain insufficient for production services
        that are spread across multiple instances or that need
        to persist keys across restarts.
        :param: locator is used to find out information on third parties when
        adding third party caveats. If this is None, no non-local third
        party caveats can be added.
        :param: key holds the private key of the oven. If this is None,
        no third party caveats may be added.
        :param: identity_client holds the identity implementation to use for
        authentication. If this is None, no authentication will be possible.
        :param: authorizer is used to check whether an authenticated user is
        allowed to perform operations. If it is None, it will use
        a ClosedAuthorizer.
        The identity parameter passed to authorizer.allow will
        always have been obtained from a call to
        IdentityClient.declared_identity.
        :param: ops_store used to persistently store the association of
        multi-op entities with their associated operations
        when oven.macaroon is called with multiple operations.
        :param: location holds the location to use when creating new macaroons.
        '''

        if checker is None:
            checker = checkers.Checker()
        root_keystore_for_ops = None
        if root_key_store is not None:
            def root_keystore_for_ops(ops):
                return root_key_store

        oven = Oven(key=key,
                    location=location,
                    locator=locator,
                    namespace=checker.namespace(),
                    root_keystore_for_ops=root_keystore_for_ops,
                    ops_store=ops_store)
        self._oven = oven

        self._checker = Checker(checker=checker, authorizer=authorizer,
                                identity_client=identity_client,
                                macaroon_opstore=oven)

    @property
    def oven(self):
        return self._oven

    @property
    def checker(self):
        return self._checker
