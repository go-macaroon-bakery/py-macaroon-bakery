# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from macaroonbakery.utils import raw_b64decode
from macaroonbakery import ThirdPartyCaveatChecker
from macaroonbakery import discharge as mdischarge


def discharge(ctx, content, key, locator, checker):
    ''' Discharges a third party caveat for legacy interaction.
    :return Macaroon
    '''
    id = content.get('id')
    if id is None:
        id = content.get('id64')
        if id is not None:
            id = raw_b64decode(id)
    caveat = content.get('caveat64')
    if caveat is not None:
        caveat = raw_b64decode(caveat)

    class ThirdPartyCaveatCheckerF(ThirdPartyCaveatChecker):
        def check_third_party_caveat(self, ctx, info):
            if checker is None:
                return []
            return checker.check_third_party_caveat(ctx, info)
    return mdischarge(ctx, id=id, caveat=caveat, key=key,
                      checker=ThirdPartyCaveatCheckerF(), locator=locator)
