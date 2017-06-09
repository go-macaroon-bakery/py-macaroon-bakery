# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from unittest import TestCase

from macaroonbakery.identity import Identity, SimpleIdentity
from macaroonbakery.checkers.caveat import Caveat
from macaroonbakery.authorizer import AuthorizerFunc, ACLAuthorizer, EVERYONE
from macaroonbakery.checker import Op


class TestAuthorizer(TestCase):
    def test_authorize_func(self):
        def f(id, op):
            self.assertEqual(id.id(), "bob")
            if op.entity == "a":
                return False, None
            elif op.entity == "b":
                return True, None
            elif op.entity == "c":
                return True, [Caveat(location="somewhere", condition="c")]
            elif op.entity == "d":
                return True, [Caveat(location="somewhere", condition="d")]
            else:
                self.fail("unexpected entity: " + op.Entity)

        ops = [Op("a", "x"), Op("b", "x"), Op("c", "x"), Op("d", "x")]
        allowed, caveats = AuthorizerFunc(f).authorize(SimpleIdentity("bob"),
                                                       ops)
        self.assertEqual(allowed, [False, True, True, True])
        self.assertEqual(caveats,
                         [
                             Caveat(location="somewhere", condition="c"),
                             Caveat(location="somewhere", condition="d")
                         ])

    def test_acl_authorizer(self):
        tests = [
            ('no ops, no problem',
             ACLAuthorizer(allow_public=True,
                           get_acl=lambda x: []), None, None, None),
            ("identity that does not implement ACLIdentity; "
             "user should be denied except for everyone group",
             ACLAuthorizer(allow_public=True,
                           get_acl=lambda op: [EVERYONE] if op.entity == 'a'
                           else ['alice']),
             SimplestIdentity('bob'),
             [Op(entity='a', action='a'), Op(entity='b', action='b')],
             [True, False]),
            ('identity that does not implement ACLIdentity with user == Id; '
             'user should be denied except for everyone group',
             ACLAuthorizer(allow_public=True,
                           get_acl=lambda op: [EVERYONE] if op.entity == 'a'
                           else ['bob']),
             SimplestIdentity("bob"),
             [Op(entity="a", action='a'), Op(entity="b", action='b')],
             [True, False]),
            ('permission denied for everyone without AllowPublic',
             ACLAuthorizer(allow_public=False,
                           get_acl=lambda op: [EVERYONE]),
             SimplestIdentity("bob"),
             [Op(entity="a", action='a')],
             [False]),
            ('permission granted to anyone with no identity with AllowPublic',
             ACLAuthorizer(allow_public=True,
                           get_acl=lambda x: [EVERYONE]),
             None,
             [Op(entity="a", action='a')],
             [True])
        ]
        for test in tests:
            allowed, caveats = test[1].authorize(test[2], test[3])
            self.assertIsNone(caveats)
            self.assertEqual(allowed, test[4])


class SimplestIdentity(Identity):
    # SimplestIdentity implements Identity for a string. Unlike
    # SimpleIdentity, it does not implement ACLIdentity.
    def __init__(self, user):
        self._identity = user

    def domain(self):
        return ""

    def id(self):
        return self._identity
