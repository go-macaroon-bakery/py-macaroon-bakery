# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

from macaroonbakery.versions import (
    VERSION_0,
    VERSION_1,
    VERSION_2,
    VERSION_3,
    LATEST_VERSION,
)
from macaroonbakery.authorizer import (
    ACLAuthorizer,
    Authorizer,
    AuthorizerFunc,
    ClosedAuthorizer,
    EVERYONE,
)
from macaroonbakery.codec import (
    decode_caveat,
    encode_caveat,
    encode_uvarint,
)
from macaroonbakery.checker import (
    AuthChecker,
    AuthInfo,
    Checker,
    LOGIN_OP,
    Op,
)
from macaroonbakery.error import (
    AuthInitError,
    CaveatNotRecognizedError,
    DischargeRequiredError,
    IdentityError,
    PermissionDenied,
    ThirdPartyCaveatCheckFailed,
    ThirdPartyInfoNotFound,
    VerificationError,
)
from macaroonbakery.identity import (
    ACLIdentity,
    Identity,
    IdentityClient,
    NoIdentities,
    SimpleIdentity,
)
from macaroonbakery.keys import (
    generate_key,
    PrivateKey,
    PublicKey,
)
from macaroonbakery.store import (
    MemoryOpsStore,
    MemoryKeyStore,
)
from macaroonbakery.third_party import (
    ThirdPartyCaveatInfo,
    ThirdPartyInfo,
    legacy_namespace,
)
from macaroonbakery.macaroon import (
    Macaroon,
    MacaroonJSONDecoder,
    MacaroonJSONEncoder,
    ThirdPartyLocator,
    ThirdPartyStore,
    macaroon_version,
)
from macaroonbakery.discharge import (
    ThirdPartyCaveatChecker,
    discharge,
    discharge_all,
    local_third_party_caveat,
)
from macaroonbakery.oven import (
    Oven,
    canonical_ops,
)
from macaroonbakery.bakery import Bakery
from macaroonbakery.utils import b64decode

__all__ = [
    'ACLAuthorizer',
    'ACLIdentity',
    'AuthChecker',
    'AuthInfo',
    'AuthInitError',
    'Authorizer',
    'AuthorizerFunc',
    'VERSION_0',
    'VERSION_1',
    'VERSION_2',
    'VERSION_3',
    'Bakery',
    'CaveatNotRecognizedError',
    'Checker',
    'ClosedAuthorizer',
    'DischargeRequiredError',
    'EVERYONE',
    'Identity',
    'IdentityClient',
    'IdentityError',
    'LATEST_VERSION',
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
    'b64decode',
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
