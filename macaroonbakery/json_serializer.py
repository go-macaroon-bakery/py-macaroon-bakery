# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
import json

from pymacaroons.macaroon import Macaroon
from pymacaroons.caveat import Caveat


class JsonSerializer(object):
    '''Serializer used to produce JSON macaroon format v1.
    '''
    def serialize(self, macaroon):
        '''Serialize the macaroon in JSON format v1.

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
                caveat_v1_to_dict(caveat) for caveat in macaroon.caveats
            ]
        return json.dumps(serialized)

    def deserialize(self, serialized):
        '''Deserialize a JSON macaroon v1.

        @param serialized the macaroon in JSON format v1.
        @return the macaroon object.
        '''
        from macaroonbakery import utils
        caveats = []
        deserialized = json.loads(serialized)

        for c in deserialized['caveats']:
            caveat = Caveat(
                caveat_id=c['cid'],
                verification_key_id=(
                    utils.raw_urlsafe_b64decode(c['vid']) if c.get('vid')
                    else None
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


def caveat_v1_to_dict(c):
    ''' Return a caveat as a dictionary for export as the JSON
    macaroon v1 format
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
