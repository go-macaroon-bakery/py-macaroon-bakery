# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import collections
import datetime

import rfc3339

from macaroonbakery.checkers.namespace import STD_NAMESPACE


class Caveat(collections.namedtuple('Caveat', 'condition location namespace')):
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

# Constants for all the standard caveat conditions.
# First and third party caveat conditions are both defined here,
# even though notionally they exist in separate name spaces.
COND_DECLARED = "declared"
COND_TIME_BEFORE = "time-before"
COND_ERROR = "error"
COND_ALLOW = "allow"
COND_DENY = "deny"
COND_NEED_DECLARED = "need-declared"


def time_before_caveat(t):
    '''Return a caveat that specifies that the time that it is checked at
    should be before t.
    '''
    return _first_party(COND_TIME_BEFORE,
                        rfc3339.rfc3339(datetime.datetime.now()))


def _first_party(name, arg):
    condition = name + " " + arg
    if arg == "":
        condition = name

    return Caveat(condition=condition,
                  namespace=STD_NAMESPACE)
