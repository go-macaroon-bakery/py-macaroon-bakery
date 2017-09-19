# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from collections import namedtuple

import macaroonbakery.checkers as checkers


def legacy_namespace():
    ''' Standard namespace for pre-version3 macaroons.
    '''
    ns = checkers.Namespace(None)
    ns.register(checkers.STD_NAMESPACE, '')
    return ns


class ThirdPartyCaveatInfo(namedtuple(
    'ThirdPartyCaveatInfo',
    'condition, first_party_public_key, third_party_key_pair, root_key, '
        'caveat, version, namespace')):
    '''ThirdPartyCaveatInfo holds the information decoded from
    a third party caveat id.

    :param: condition holds the third party condition to be discharged.
    This is the only field that most third party dischargers will
    need to consider.

    :param: first_party_public_key 	holds the nacl public key of the party
    that created the third party caveat.

    :param: third_party_key_pair holds the nacl private used to decrypt
    the caveat - the key pair of the discharging service.

    :param: root_key bytes holds the secret root key encoded by the caveat.

    :param: caveat holds the full encoded base64 string caveat id from
    which all the other fields are derived.

    :param: version holds the version that was used to encode
    the caveat id.

    :param: namespace object that holds the namespace of the first party
    that created the macaroon, as encoded by the party that added the
    third party caveat.
    '''


class ThirdPartyInfo(namedtuple('ThirdPartyInfo', 'version, public_key')):
    ''' ThirdPartyInfo holds information on a given third party
    discharge service.
    version holds latest the bakery protocol version supported
    by the discharger.
    public_key holds the public nacl key of the third party.
    '''
