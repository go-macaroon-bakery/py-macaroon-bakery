# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from unittest import TestCase

import copy
from datetime import datetime, timedelta

import macaroonbakery

EPOCH = datetime(1900, 11, 17, 19, 00, 13, 0, None)
AGES = EPOCH + timedelta(days=10)


class TestOven(TestCase):
    def test_canonical_ops(self):
        canonical_ops_tests = (
            ('empty array', [], []),
            ('one element', [macaroonbakery.Op('a', 'a')],
             [macaroonbakery.Op('a', 'a')]),
            ('all in order',
             [macaroonbakery.Op('a', 'a'), macaroonbakery.Op('a', 'b'),
              macaroonbakery.Op('c', 'c')],
             [macaroonbakery.Op('a', 'a'), macaroonbakery.Op('a', 'b'),
              macaroonbakery.Op('c', 'c')]),
            ('out of order',
             [macaroonbakery.Op('c', 'c'), macaroonbakery.Op('a', 'b'),
              macaroonbakery.Op('a', 'a')],
             [macaroonbakery.Op('a', 'a'), macaroonbakery.Op('a', 'b'),
              macaroonbakery.Op('c', 'c')]),
            ('with duplicates',
             [macaroonbakery.Op('c', 'c'), macaroonbakery.Op('a', 'b'),
              macaroonbakery.Op('a', 'a'), macaroonbakery.Op('c', 'a'),
              macaroonbakery.Op('c', 'b'), macaroonbakery.Op('c', 'c'),
              macaroonbakery.Op('a', 'a')],
             [macaroonbakery.Op('a', 'a'), macaroonbakery.Op('a', 'b'),
              macaroonbakery.Op('c', 'a'), macaroonbakery.Op('c', 'b'),
              macaroonbakery.Op('c', 'c')]),
            ('make sure we\'ve got the fields right',
             [macaroonbakery.Op(entity='read', action='two'),
              macaroonbakery.Op(entity='read', action='one'),
              macaroonbakery.Op(entity='write', action='one')],
             [macaroonbakery.Op(entity='read', action='one'),
              macaroonbakery.Op(entity='read', action='two'),
              macaroonbakery.Op(entity='write', action='one')])
        )
        for about, ops, expected in canonical_ops_tests:
            new_ops = copy.copy(ops)
            canonical_ops = macaroonbakery.canonical_ops(new_ops)
            self.assertEquals(canonical_ops, expected)
            # Verify that the original array isn't changed.
            self.assertEquals(new_ops, ops)

    def test_multiple_ops(self):
        test_oven = macaroonbakery.Oven(
            ops_store=macaroonbakery.MemoryOpsStore())
        ops = [macaroonbakery.Op('one', 'read'),
               macaroonbakery.Op('one', 'write'),
               macaroonbakery.Op('two', 'read')]
        m = test_oven.macaroon(macaroonbakery.LATEST_BAKERY_VERSION, AGES,
                               None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon])
        self.assertEquals(len(conds), 1)  # time-before caveat.
        self.assertEquals(macaroonbakery.canonical_ops(got_ops), ops)

    def test_multiple_ops_in_id(self):
        test_oven = macaroonbakery.Oven()
        ops = [macaroonbakery.Op('one', 'read'),
               macaroonbakery.Op('one', 'write'),
               macaroonbakery.Op('two', 'read')]
        m = test_oven.macaroon(macaroonbakery.LATEST_BAKERY_VERSION, AGES,
                               None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon])
        self.assertEquals(len(conds), 1)  # time-before caveat.
        self.assertEquals(macaroonbakery.canonical_ops(got_ops), ops)

    def test_multiple_ops_in_id_with_version1(self):
        test_oven = macaroonbakery.Oven()
        ops = [macaroonbakery.Op('one', 'read'),
               macaroonbakery.Op('one', 'write'),
               macaroonbakery.Op('two', 'read')]
        m = test_oven.macaroon(macaroonbakery.BAKERY_V1, AGES, None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon])
        self.assertEquals(len(conds), 1)  # time-before caveat.
        self.assertEquals(macaroonbakery.canonical_ops(got_ops), ops)

    def test_huge_number_of_ops_gives_small_macaroon(self):
        test_oven = macaroonbakery.Oven(
            ops_store=macaroonbakery.MemoryOpsStore())
        ops = []
        for i in range(30000):
            ops.append(macaroonbakery.Op(entity='entity{}'.format(i),
                                         action='action{}'.format(i)))

        m = test_oven.macaroon(macaroonbakery.LATEST_BAKERY_VERSION, AGES,
                               None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon])
        self.assertEquals(len(conds), 1)  # time-before caveat.
        self.assertEquals(macaroonbakery.canonical_ops(got_ops),
                          macaroonbakery.canonical_ops(ops))

        data = m.serialize_json()
        self.assertLess(len(data), 300)

    def test_ops_stored_only_once(self):
        st = macaroonbakery.MemoryOpsStore()
        test_oven = macaroonbakery.Oven(ops_store=st)

        ops = [macaroonbakery.Op('one', 'read'),
               macaroonbakery.Op('one', 'write'),
               macaroonbakery.Op('two', 'read')]

        m = test_oven.macaroon(macaroonbakery.LATEST_BAKERY_VERSION, AGES,
                               None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon])
        self.assertEquals(macaroonbakery.canonical_ops(got_ops),
                          macaroonbakery.canonical_ops(ops))

        # Make another macaroon containing the same ops in a different order.
        ops = [macaroonbakery.Op('one', 'write'),
               macaroonbakery.Op('one', 'read'),
               macaroonbakery.Op('one', 'read'),
               macaroonbakery.Op('two', 'read')]
        test_oven.macaroon(macaroonbakery.LATEST_BAKERY_VERSION, AGES, None,
                           ops)
        self.assertEquals(len(st._store), 1)
