# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from macaroonbakery.checkers.auth_context import ContextKey


TIME_KEY = ContextKey('time-key')


def context_with_clock(ctx, clock):
    ''' Returns a copy of ctx with a key added that associates it with the given
    clock implementation, which will be used by the time-before checker
    to determine the current time.
    The clock should have a utcnow method that returns the current time
    as a datetime value in UTC.
    '''
    if clock is None:
        return ctx
    return ctx.with_value(TIME_KEY, clock)
