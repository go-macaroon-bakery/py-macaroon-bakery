# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import pyrfc3339

from macaroonbakery.checkers.auth_context import ContextKey
from macaroonbakery.checkers.conditions import COND_TIME_BEFORE, STD_NAMESPACE
from macaroonbakery.checkers.utils import condition_with_prefix
from macaroonbakery.checkers.caveat import parse_caveat


TIME_KEY = ContextKey('time-key')


def context_with_clock(ctx, clock):
    ''' Returns a copy of ctx with a key added that associates it with the
    given clock implementation, which will be used by the time-before checker
    to determine the current time.
    The clock should have a utcnow method that returns the current time
    as a datetime value in UTC.
    '''
    if clock is None:
        return ctx
    return ctx.with_value(TIME_KEY, clock)


def macaroons_expiry_time(ns, ms):
    ''' Returns the minimum time of any time-before caveats found in the given
    macaroons orr None if such caveats not found.
    :param ns:
    :param ms:
    :return:
    '''
    t = None
    for m in ms:
        et = expiry_time(ns, m.caveats)
        if et is not None:
            if t is None or et < t:
                t = et
    return t


def expiry_time(ns, cavs):
    ''' Returns the minimum time of any time-before caveats found
    in the given list or Nonne if such caveats not found.

    The ns parameter is
    :param ns: used to determine the standard namespace prefix - if
    the standard namespace is not found, the empty prefix is assumed.
    :param cavs: a list of Caveats
    :return: time
    '''
    prefix = ns.resolve(STD_NAMESPACE)
    time_before_cond = condition_with_prefix(
        prefix, COND_TIME_BEFORE)
    t = None
    for cav in cavs:
        cav = cav.caveat_id_bytes.decode('utf-8')
        name, rest = parse_caveat(cav)
        if name != time_before_cond:
            continue
        try:
            et = pyrfc3339.parse(rest)
            if t is None or et < t:
                t = et
        except ValueError:
            continue
    return t
