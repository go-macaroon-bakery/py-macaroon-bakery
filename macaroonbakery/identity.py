# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import abc


class Identity(object):
    ''' Holds identity information declared in a first party caveat added when
    discharging a third party caveat.
    '''
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def id(self):
        ''' Returns the id of the user.

        May be an opaque blob with no human meaning. An id is only considered
        to be unique with a given domain.
        :return string
        '''
        raise NotImplementedError('id method must be defined in subclass')

    @abc.abstractmethod
    def domain(self):
        '''Return the domain of the user.

        This will be empty if the user was authenticated
        directly with the identity provider.
        :return string
        '''
        raise NotImplementedError('domain method must be defined in subclass')


class ACLIdentity(Identity):
    ''' ACLIdentity may be implemented by Identity implementations
    to report group membership information.
    '''
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def allow(self, acls):
        ''' reports whether the user should be allowed to access
        any of the users or groups in the given acl list.
        :param acls array of string acl
        :return boolean
        '''
        raise NotImplementedError('allow method must be defined in subclass')


class SimpleIdentity(ACLIdentity):
    ''' A simple form of identity where the user is represented by a string.
    '''
    def __init__(self, user):
        self._identity = user

    def domain(self):
        ''' A simple identity has no domain.
        '''
        return ""

    def id(self):
        '''Return the user name as the id.
        '''
        return self._identity

    def allow(self, acls):
        '''Allow access to any ACL members that was equal to the user name.

        That is, some user u is considered a member of group u and no other.
        '''
        for acl in acls:
            if self._identity == acl:
                return True
        return False
