# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
import json
import webbrowser

from pymacaroons import Macaroon

from macaroonbakery import json_serializer


def deserialize(json_macaroon):
    '''Deserialize a JSON macaroon into a macaroon object from pymacaroons.

    @param the JSON macaroon to deserialize as a dict.
    @return the deserialized macaroon object.
    '''
    return Macaroon.deserialize(json.dumps(json_macaroon),
                                json_serializer.JsonSerializer())


def serialize_macaroon_string(macaroon):
    '''Serialize macaroon object to string.

    @param macaroon object to be serialized.
    @return a string serialization form of the macaroon.
    '''
    return macaroon.serialize(json_serializer.JsonSerializer())


def add_base64_padding(b):
    '''Add padding to base64 encoded bytes.

    pymacaroons does not give padded base64 bytes from serialization.

    @param bytes b to be padded.
    @return a padded bytes.
    '''
    return b + b'=' * (-len(b) % 4)


def remove_base64_padding(b):
    '''Remove padding from base64 encoded bytes.

    pymacaroons does not give padded base64 bytes from serialization.

    @param bytes b to be padded.
    @return a padded bytes.
    '''

    return b.rstrip(b'=')


def raw_urlsafe_b64decode(s):
    '''Base64 decode with added padding and convertion to bytes.

    @param s string decode
    @return bytes decoded
    '''
    return base64.urlsafe_b64decode(add_base64_padding(
        s.encode('ascii')))


def raw_urlsafe_b64encode(b):
    '''Base64 encode with padding removed.

    @param s string decode
    @return bytes decoded
    '''
    return remove_base64_padding(base64.urlsafe_b64encode(b))


def visit_page_with_browser(visit_url):
    '''Open a browser so the user can validate its identity.

    @param visit_url: where to prove your identity.
    '''
    webbrowser.open(visit_url, new=1)
