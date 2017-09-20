# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from six.moves.urllib.parse import urlparse
import requests

import macaroonbakery


class ThirdPartyLocator(macaroonbakery.ThirdPartyLocator):
    ''' Implements macaroonbakery.ThirdPartyLocator by first looking in the
    backing cache and, if that fails, making an HTTP request to find the
    information associated with the given discharge location.
    '''

    def __init__(self, allow_insecure=False):
        '''
        @param url: the url to retrieve public_key
        @param allow_insecure: By default it refuses to use insecure URLs.
        '''
        self._allow_insecure = allow_insecure
        self._cache = {}

    def third_party_info(self, loc):
        u = urlparse(loc)
        if u.scheme != 'https' and not self._allow_insecure:
            raise macaroonbakery.ThirdPartyInfoNotFound(
                'untrusted discharge URL {}'.format(loc))
        loc = loc.rstrip('/')
        info = self._cache.get(loc)
        if info is not None:
            return info
        url_endpoint = '/discharge/info'
        resp = requests.get(loc + url_endpoint)
        status_code = resp.status_code
        if status_code == 404:
            url_endpoint = '/publickey'
            resp = requests.get(loc + url_endpoint)
            status_code = resp.status_code
        if status_code != 200:
            raise macaroonbakery.ThirdPartyInfoNotFound(
                'unable to get info from {}'.format(url_endpoint))
        json_resp = resp.json()
        if json_resp is None:
            raise macaroonbakery.ThirdPartyInfoNotFound(
                'no response from /discharge/info')
        pk = json_resp.get('PublicKey')
        if pk is None:
            raise macaroonbakery.ThirdPartyInfoNotFound(
                'no public key found in /discharge/info')
        idm_pk = macaroonbakery.PublicKey.deserialize(pk)
        version = json_resp.get('Version', macaroonbakery.BAKERY_V1)
        self._cache[loc] = macaroonbakery.ThirdPartyInfo(
            version=version,
            public_key=idm_pk
        )
        return self._cache.get(loc)
