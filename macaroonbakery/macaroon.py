# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
import logging
import os

import pymacaroons
from pymacaroons.serializers import json_serializer


from macaroonbakery import (
    BAKERY_V0, BAKERY_V1, BAKERY_V3, LATEST_BAKERY_VERSION
)
from macaroonbakery import codec

log = logging.getLogger(__name__)


class Macaroon(object):
    '''Represent an undischarged macaroon along with its first
    party caveat namespace and associated third party caveat information
    which should be passed to the third party when discharging a caveat.
    '''
    def __init__(self, root_key, id, location=None,
                 version=LATEST_BAKERY_VERSION, ns=None):
        '''Creates a new macaroon with the given root key, id and location.

        If the version is more than the latest known version,
        the latest known version will be used. The namespace should hold the
        namespace of the service that is creating the macaroon.
        @param root_key bytes or string
        @param id bytes or string
        @param location bytes or string
        @param version the bakery version.
        @param ns
        '''
        if version > LATEST_BAKERY_VERSION:
            log.info('use last known version:{} instead of: {}'.format(
                LATEST_BAKERY_VERSION, version
            ))
            version = LATEST_BAKERY_VERSION
        # m holds the underlying macaroon.
        self._macaroon = pymacaroons.Macaroon(
            location=location, key=root_key, identifier=id,
            version=macaroon_version(version))
        # version holds the version of the macaroon.
        self._version = version
        self._caveat_data = {}
        self._ns = ns
        self._caveat_id_prefix = bytearray()

    def macaroon(self):
        ''' Return the underlying macaroon.
        '''
        return self._macaroon

    def version(self):
        return self._version

    def namespace(self):
        return self._ns

    def caveat_data(self):
        return self._caveat_data

    def add_caveat(self, cav, key=None, loc=None):
        '''Add a caveat to the macaroon.

        It encrypts it using the given key pair
        and by looking up the location using the given locator.
        As a special case, if the caveat's Location field has the prefix
        "local " the caveat is added as a client self-discharge caveat using
        the public key base64-encoded in the rest of the location. In this
        case, the Condition field must be empty. The resulting third-party
        caveat will encode the condition "true" encrypted with that public
        key.

        @param cav the checkers.Caveat to be added.
        @param key the nacl public key to encrypt third party caveat.
        @param loc locator to find information on third parties when adding
        third party caveats. It is expected to have a third_party_info method
        that will be called with a location string and should return a
        ThirdPartyInfo instance holding the requested information.
        '''
        if cav.location is None:
            self._macaroon.add_first_party_caveat(cav.condition)
            return
        if key is None:
            raise ValueError(
                'no private key to encrypt third party caveat')
        local_info, ok = parse_local_location(cav.location)
        if ok:
            info = local_info
            cav.location = 'local'
            if cav.condition is not '':
                raise ValueError(
                    'cannot specify caveat condition in '
                    'local third-party caveat')
            cav.condition = 'true'
        else:
            if loc is None:
                raise ValueError(
                    'no locator when adding third party caveat')
            info = loc.third_party_info(cav.location)
            if info is None:
                raise ValueError(
                    'cannot find public key for location {}'.format(
                        cav.location)
                )
            root_key = os.urandom(24)
        # Use the least supported version to encode the caveat.
        if self._version < info.version:
            info.version = self._version

        caveat_info = codec.encode_caveat(cav.condition, root_key, info,
                                          key, self._ns)
        if info.version < BAKERY_V3:
            # We're encoding for an earlier client or third party which does
            # not understand bundled caveat info, so use the encoded
            # caveat information as the caveat id.
            id = caveat_info
        else:
            id = self._new_caveat_id(self._caveat_id_prefix)
            self._caveat_data[id] = caveat_info

        self._macaroon.add_third_party_caveat(cav.location, root_key, id)

    def add_caveats(self, cavs, key, loc):
        '''Add an array of caveats to the macaroon.

        This method does not mutate the current object.
        @param cavs arrary of caveats.
        @param key the nacl public key to encrypt third party caveat.
        @param loc locator to find the location object that has a method
        third_party_info.
        '''
        if cavs is None:
            return
        for cav in cavs:
            self.add_caveat(cav, key, loc)

    def serialize_json(self):
        '''Return a dictionary holding the macaroon data in JSON format.

        Note that this differs from the underlying macaroon serialize method as
        it does not return a string. This makes it easier to incorporate the
        macaroon into other JSON objects.

        @return a dictionary holding the macaroon data in JSON format
        '''
        serialized = {
            'm': self._macaroon.serialize(
                json_serializer.JsonSerializer()),
            'v': self._version,
        }
        if self._ns is not None:
            serialized['ns'] = self._ns.serialize()
        return serialized

    def _new_caveat_id(self, base):
        '''Return a third party caveat id

        This does not duplicate any third party caveat ids already inside
        macaroon. If base is non-empty, it is used as the id prefix.

        @param base bytes
        @return bytes
        '''
        id = bytearray()
        if len(base) > 0:
            id.append(base)
        else:
            # Add a version byte to the caveat id. Technically
            # this is unnecessary as the caveat-decoding logic
            # that looks at versions should never see this id,
            # but if the caveat payload isn't provided with the
            # payload, having this version gives a strong indication
            # that the payload has been omitted so we can produce
            # a better error for the user.
            id.append(BAKERY_V3)

        # Iterate through integers looking for one that isn't already used,
        # starting from n so that if everyone is using this same algorithm,
        # we'll only perform one iteration.
        i = len(self._caveat_data)
        caveats = self._macaroon.caveats
        while True:
            # We append a varint to the end of the id and assume that
            # any client that's created the id that we're using as a base
            # is using similar conventions - in the worst case they might
            # end up with a duplicate third party caveat id and thus create
            # a macaroon that cannot be discharged.
            temp = id[:]
            codec.encode_uvarint(i, temp)
            for cav in caveats:
                if cav.verification_id is not None and cav.caveat_id == temp:
                    i += 1
                    break
            return bytes(temp)

    def first_party_caveats(self):
        '''Return the first party caveats from this macaroon.

        @return the first party caveats from this macaroon as pymacaroons
        caveats.
        '''
        return self._macaroon.first_party_caveats()

    def third_party_caveats(self):
        '''Return the third party caveats.

        @return the third party caveats as pymacaroons caveats.
        '''
        return self._macaroon.third_party_caveats()


def macaroon_version(bakery_version):
    '''Return the macaroon version given the bakery version.

    @param bakery_version the bakery version
    @return macaroon_version the derived macaroon version
    '''
    if bakery_version in [BAKERY_V0, BAKERY_V1]:
        return pymacaroons.MACAROON_V1
    return pymacaroons.MACAROON_V2


def parse_local_location(loc):
    '''Parse a local caveat location as generated by LocalThirdPartyCaveat.

    This is of the form:

        local <version> <pubkey>

    where <version> is the bakery version of the client that we're
    adding the local caveat for.

    It returns false if the location does not represent a local
    caveat location.
    @return a tuple of location and if the location is local.
    '''
    if not(loc.startswith('local ')):
        return (), False
    v = BAKERY_V1
    fields = loc.split()
    fields = fields[1:]  # Skip 'local'
    if len(fields) == 2:
        try:
            v = int(fields[0])
        except ValueError:
            return (), False
        fields = fields[1:]
    if len(fields) == 1:
        return (base64.b64decode(fields[0]), v), True
    return (), False


class ThirdPartyLocator(object):
    '''Used to find information on third party discharge services.
    '''
    def __init__(self):
        self._store = {}

    def third_party_info(self, loc):
        '''Return information on the third party at the given location.

        It returns None if no match is found.

        @param loc string
        @return: string
        '''
        return self._store.get(loc)

    def add_info(self, loc, info):
        '''Associates the given information with the given location.

        It will ignore any trailing slash.
        '''
        self._store[loc.rstrip('\\')] = info
