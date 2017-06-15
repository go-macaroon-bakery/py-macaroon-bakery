# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import collections

_Caveat = collections.namedtuple('Caveat', 'condition location namespace')


class Caveat(_Caveat):
    '''Represents a condition that must be true for a check to complete
    successfully.

    If location is provided, the caveat must be discharged by
    a third party at the given location (a URL string).

    The namespace parameter holds the namespace URI string of the
    condition - if it is provided, it will be converted to a namespace prefix
    before adding to the macaroon.
    '''
    __slots__ = ()

    def __new__(cls, condition, location=None, namespace=None):
        return super(Caveat, cls).__new__(cls, condition, location, namespace)
