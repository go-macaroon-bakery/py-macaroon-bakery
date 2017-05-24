# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
import json
import utils

from pymacaroons.utils import convert_to_bytes
from pymacaroons.macaroon import Macaroon
from pymacaroons.caveat import Caveat


class JsonSerializer(object):
    ''' Serializer used to produce JSON macaroon format v1.
    '''
    def serialize(self, macaroon):
        ''' serialize the macaroon in JSON format v1.
        @param macaroon the macaroon to serialize.
        @return JSON macaroon.
        '''
        serialized = {
            'identifier': macaroon.identifier,
            'signature': macaroon.signature
        }
        if macaroon.location:
            serialized['location'] = macaroon.location
        if macaroon.caveats:
            serialized['caveats'] = [
                caveat_to_dict(caveat) for caveat in macaroon.caveats
            ]
        return json.dumps(serialized)

    def deserialize(self, serialized):
        ''' Deserialize a JSON macaroon v1.

        @param serialized the macaroon in JSON format v1.
        @return the macaroon object.
        '''
        caveats = []
        deserialized = json.loads(serialized)

        for c in deserialized['caveats']:
            caveat = Caveat(
                caveat_id=c['cid'],
                verification_key_id=(
                    raw_b64decode(c['vid']) if c.get('vid') else None
                ),
                location=(
                    c['cl'] if c.get('cl') else None
                )
            )
            caveats.append(caveat)

        return Macaroon(
            location=deserialized['location'],
            identifier=deserialized['identifier'],
            caveats=caveats,
            signature=deserialized['signature']
        )


def raw_b64decode(s):
    ''' Base64 decode with added padding and convertion to bytes.

    @param s string decode
    @return bytes decoded
    '''
    return base64.urlsafe_b64decode(utils.add_base64_padding(
        convert_to_bytes(s)))


def caveat_to_dict(c):
    ''' Caveat to dictionnary for the JSON macaroon V1 format.

    @param c the caveat object.
    @return JSON caveat in V1 macaroon format.
    '''
    serialized = {}
    if len(c.caveat_id) > 0:
        serialized['cid'] = c.caveat_id
    if c.verification_key_id:
        serialized['vid'] = base64.urlsafe_b64encode(
            c.verification_key_id).decode('ascii')
    if c.location:
        serialized['cl'] = c.location
    return serialized
