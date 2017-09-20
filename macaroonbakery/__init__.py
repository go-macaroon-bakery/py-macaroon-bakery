# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

from __future__ import unicode_literals
try:
    import urllib3.contrib.pyopenssl
except ImportError:
    pass
else:
    urllib3.contrib.pyopenssl.inject_into_urllib3()

from macaroonbakery.versions import (
    LATEST_BAKERY_VERSION, BAKERY_V3, BAKERY_V2, BAKERY_V1, BAKERY_V0
)
from macaroonbakery.authorizer import (
    ClosedAuthorizer, EVERYONE, AuthorizerFunc, Authorizer, ACLAuthorizer
)
from macaroonbakery.codec import (
    encode_caveat, decode_caveat, encode_uvarint
)
from macaroonbakery.checker import (
    Op, LOGIN_OP, AuthInfo, AuthChecker, Checker
)
from macaroonbakery.error import (
    ThirdPartyCaveatCheckFailed, CaveatNotRecognizedError, AuthInitError,
    PermissionDenied, IdentityError, DischargeRequiredError, VerificationError,
    ThirdPartyInfoNotFound
)
from macaroonbakery.identity import (
    Identity, ACLIdentity, SimpleIdentity, IdentityClient, NoIdentities
)
from macaroonbakery.keys import generate_key, PrivateKey, PublicKey
from macaroonbakery.store import MemoryOpsStore, MemoryKeyStore
from macaroonbakery.third_party import (
    ThirdPartyCaveatInfo, ThirdPartyInfo, legacy_namespace
)
from macaroonbakery.macaroon import (
    Macaroon, MacaroonJSONDecoder, MacaroonJSONEncoder, ThirdPartyStore,
    ThirdPartyLocator, macaroon_version
)
from macaroonbakery.discharge import (
    discharge_all, discharge, local_third_party_caveat, ThirdPartyCaveatChecker
)
from macaroonbakery.oven import Oven, canonical_ops
from macaroonbakery.bakery import Bakery


__all__ = [
    'ACLIdentity',
    'ACLAuthorizer',
    'AuthChecker',
    'AuthInfo',
    'AuthInitError',
    'Authorizer',
    'AuthorizerFunc',
    'Bakery',
    'BAKERY_V0',
    'BAKERY_V1',
    'BAKERY_V2',
    'BAKERY_V3',
    'Bakery',
    'CaveatNotRecognizedError',
    'Checker',
    'ClosedAuthorizer',
    'DischargeRequiredError',
    'EVERYONE',
    'Identity',
    'IdentityClient',
    'IdentityError',
    'LATEST_BAKERY_VERSION',
    'LOGIN_OP',
    'Macaroon',
    'MacaroonJSONDecoder',
    'MacaroonJSONEncoder',
    'MemoryKeyStore',
    'MemoryOpsStore',
    'NoIdentities',
    'Op',
    'Oven',
    'PermissionDenied',
    'PrivateKey',
    'PublicKey',
    'NoIdentities',
    'SimpleIdentity',
    'ThirdPartyCaveatCheckFailed',
    'ThirdPartyCaveatChecker',
    'ThirdPartyCaveatInfo',
    'ThirdPartyInfo',
    'ThirdPartyInfoNotFound',
    'ThirdPartyLocator',
    'ThirdPartyStore',
    'VERSION',
    'VerificationError',
    'canonical_ops',
    'decode_caveat',
    'discharge',
    'discharge_all',
    'encode_caveat',
    'encode_uvarint',
    'generate_key',
    'legacy_namespace',
    'local_third_party_caveat',
    'macaroon_version',
]
