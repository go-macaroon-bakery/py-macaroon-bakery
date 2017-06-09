# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from collections import namedtuple


class Op(namedtuple('Op', 'entity, action')):
    ''' Op holds an entity and action to be authorized on that entity.
    '''
    __slots__ = ()

    def __new__(cls, entity, action):
        '''

        @param entity string holds the name of the entity to be authorized.
        Entity names should not contain spaces and should
        not start with the prefix "login" or "multi-" (conventionally,
        entity names will be prefixed with the entity type followed
        by a hyphen.

        @param action string holds the action to perform on the entity,
        such as "read" or "delete". It is up to the service using a checker
        to define a set of operations and keep them consistent over time.

        '''
        return super(Op, cls).__new__(cls, entity, action)

    def __key(self):
        return self.entity, self.action

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.__key() == other.__key()

    def __hash__(self):
        return hash(self.__key())


LOGIN_OP = Op(entity="login", action="login")
