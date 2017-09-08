# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from unittest import TestCase

import macaroonbakery
import macaroonbakery.checkers as checkers


class TestAuthorizer(TestCase):
    def test_authorize_func(self):
        def f(ctx, identity, op):
            self.assertEqual(identity.id(), 'bob')
            if op.entity == 'a':
                return False, None
            elif op.entity == 'b':
                return True, None
            elif op.entity == 'c':
                return True, [checkers.Caveat(location='somewhere',
                                              condition='c')]
            elif op.entity == 'd':
                return True, [checkers.Caveat(location='somewhere',
                                              condition='d')]
            else:
                self.fail('unexpected entity: ' + op.Entity)

        ops = [macaroonbakery.Op('a', 'x'), macaroonbakery.Op('b', 'x'),
               macaroonbakery.Op('c', 'x'), macaroonbakery.Op('d', 'x')]
        allowed, caveats = macaroonbakery.AuthorizerFunc(f).authorize(
            checkers.AuthContext(),
            macaroonbakery.SimpleIdentity('bob'),
            ops
        )
        self.assertEqual(allowed, [False, True, True, True])
        self.assertEqual(caveats, [
            checkers.Caveat(location='somewhere', condition='c'),
            checkers.Caveat(location='somewhere', condition='d')
        ])

    def test_acl_authorizer(self):
        ctx = checkers.AuthContext()
        tests = [
            ('no ops, no problem',
             macaroonbakery.ACLAuthorizer(allow_public=True,
                                          get_acl=lambda x, y: []), None, [],
             []),
            ('identity that does not implement ACLIdentity; '
             'user should be denied except for everyone group',
             macaroonbakery.ACLAuthorizer(allow_public=True,
                                          get_acl=lambda ctx, op: [
                                              macaroonbakery.EVERYONE]
                                          if op.entity == 'a' else ['alice']),
             SimplestIdentity('bob'),
             [macaroonbakery.Op(entity='a', action='a'),
              macaroonbakery.Op(entity='b', action='b')],
             [True, False]),
            ('identity that does not implement ACLIdentity with user == Id; '
             'user should be denied except for everyone group',
             macaroonbakery.ACLAuthorizer(allow_public=True,
                                          get_acl=lambda ctx, op: [
                                              macaroonbakery.EVERYONE] if
                                          op.entity == 'a' else ['bob']),
             SimplestIdentity('bob'),
             [macaroonbakery.Op(entity='a', action='a'),
              macaroonbakery.Op(entity='b', action='b')],
             [True, False]),
            ('permission denied for everyone without AllowPublic',
             macaroonbakery.ACLAuthorizer(allow_public=False,
                                          get_acl=lambda x, y: [
                                              macaroonbakery.EVERYONE]),
             SimplestIdentity('bob'),
             [macaroonbakery.Op(entity='a', action='a')],
             [False]),
            ('permission granted to anyone with no identity with AllowPublic',
             macaroonbakery.ACLAuthorizer(allow_public=True,
                                          get_acl=lambda x, y: [
                                              macaroonbakery.EVERYONE]),
             None,
             [macaroonbakery.Op(entity='a', action='a')],
             [True])
        ]
        for test in tests:
            allowed, caveats = test[1].authorize(ctx, test[2], test[3])
            self.assertEqual(len(caveats), 0)
            self.assertEqual(allowed, test[4])

    def test_context_wired_properly(self):
        ctx = checkers.AuthContext({'a': 'aval'})

        class Visited:
            in_f = False
            in_allow = False
            in_get_acl = False

        def f(ctx, identity, op):
            self.assertEqual(ctx.get('a'), 'aval')
            Visited.in_f = True
            return False, None

        macaroonbakery.AuthorizerFunc(f).authorize(
            ctx, macaroonbakery.SimpleIdentity('bob'), ['op1']
        )
        self.assertTrue(Visited.in_f)

        class TestIdentity(SimplestIdentity, macaroonbakery.ACLIdentity):
            def allow(other, ctx, acls):
                self.assertEqual(ctx.get('a'), 'aval')
                Visited.in_allow = True
                return False

        def get_acl(ctx, acl):
            self.assertEqual(ctx.get('a'), 'aval')
            Visited.in_get_acl = True
            return []

        macaroonbakery.ACLAuthorizer(allow_public=False,
                                     get_acl=get_acl).authorize(
            ctx, TestIdentity('bob'), ['op1'])
        self.assertTrue(Visited.in_get_acl)
        self.assertTrue(Visited.in_allow)


class SimplestIdentity(macaroonbakery.Identity):
    # SimplestIdentity implements Identity for a string. Unlike
    # SimpleIdentity, it does not implement ACLIdentity.
    def __init__(self, user):
        self._identity = user

    def domain(self):
        return ''

    def id(self):
        return self._identity
