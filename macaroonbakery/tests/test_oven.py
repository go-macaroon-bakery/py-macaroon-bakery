# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

from unittest import TestCase

import copy
from datetime import datetime, timedelta

from macaroonbakery import (
    BAKERY_V1, LATEST_BAKERY_VERSION, checker, oven, store
)

EPOCH = datetime(1900, 11, 17, 19, 00, 13, 0, None)
AGES = EPOCH + timedelta(days=10)


class TestOven(TestCase):
    def test_canonical_ops(self):
        canonical_ops_tests = (
            ("empty array", [], []),
            ("one element", [checker.Op("a", "a")], [checker.Op("a", "a")]),
            ("all in order",
             [checker.Op("a", "a"), checker.Op("a", "b"),
              checker.Op("c", "c")],
             [checker.Op("a", "a"), checker.Op("a", "b"),
              checker.Op("c", "c")]),
            ("out of order",
             [checker.Op("c", "c"), checker.Op("a", "b"),
              checker.Op("a", "a")],
             [checker.Op("a", "a"), checker.Op("a", "b"),
              checker.Op("c", "c")]),
            ("with duplicates",
             [checker.Op("c", "c"), checker.Op("a", "b"),
              checker.Op("a", "a"), checker.Op("c", "a"),
              checker.Op("c", "b"), checker.Op("c", "c"),
              checker.Op("a", "a")],
             [checker.Op("a", "a"), checker.Op("a", "b"),
              checker.Op("c", "a"), checker.Op("c", "b"),
              checker.Op("c", "c")]),
            ("make sure we've got the fields right",
             [checker.Op(entity="read", action="two"),
              checker.Op(entity="read", action="one"),
              checker.Op(entity="write", action="one")],
             [checker.Op(entity="read", action="one"),
              checker.Op(entity="read", action="two"),
              checker.Op(entity="write", action="one")])
        )
        for about, ops, expected in canonical_ops_tests:
            new_ops = copy.copy(ops)
            canonical_ops = oven.canonical_ops(new_ops)
            self.assertEquals(canonical_ops, expected)
            # Verify that the original array isn't changed.
            self.assertEquals(new_ops, ops)

    def test_multiple_ops(self):
        test_oven = oven.Oven(ops_store=store.MemoryOpsStore())
        ops = [checker.Op("one", "read"), checker.Op("one", "write"),
               checker.Op("two", "read")]
        m = test_oven.macaroon(LATEST_BAKERY_VERSION, AGES, None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon()])
        self.assertEquals(len(conds), 1)  # time-before caveat.
        self.assertEquals(oven.canonical_ops(got_ops), ops)

    def test_multiple_ops_in_id(self):
        test_oven = oven.Oven()
        ops = [checker.Op("one", "read"), checker.Op("one", "write"),
               checker.Op("two", "read")]
        m = test_oven.macaroon(LATEST_BAKERY_VERSION, AGES, None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon()])
        self.assertEquals(len(conds), 1)  # time-before caveat.
        self.assertEquals(oven.canonical_ops(got_ops), ops)

    def test_multiple_ops_in_id_with_version1(self):
        test_oven = oven.Oven()
        ops = [checker.Op("one", "read"), checker.Op("one", "write"),
               checker.Op("two", "read")]
        m = test_oven.macaroon(BAKERY_V1, AGES, None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon()])
        self.assertEquals(len(conds), 1)  # time-before caveat.
        self.assertEquals(oven.canonical_ops(got_ops), ops)

    def test_huge_number_of_ops_gives_small_macaroon(self):
        test_oven = oven.Oven(ops_store=store.MemoryOpsStore())
        ops = []
        for i in range(30000):
            ops.append(checker.Op(entity="entity{}".format(i),
                                  action="action{}".format(i)))

        m = test_oven.macaroon(LATEST_BAKERY_VERSION, AGES, None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon()])
        self.assertEquals(len(conds), 1)  # time-before caveat.
        self.assertEquals(oven.canonical_ops(got_ops), oven.canonical_ops(ops))

        data = m.serialize_json()
        self.assertLess(len(data), 300)

    def test_ops_stored_only_once(self):
        st = store.MemoryOpsStore()
        test_oven = oven.Oven(ops_store=st)

        ops = [checker.Op("one", "read"), checker.Op("one", "write"),
               checker.Op("two", "read")]

        m = test_oven.macaroon(LATEST_BAKERY_VERSION, AGES, None, ops)
        got_ops, conds = test_oven.macaroon_ops([m.macaroon()])
        self.assertEquals(oven.canonical_ops(got_ops),
                          oven.canonical_ops(ops))

        # Make another macaroon containing the same ops in a different order.
        ops = [checker.Op("one", "write"), checker.Op("one", "read"),
               checker.Op("one", "read"), checker.Op("two", "read")]
        test_oven.macaroon(LATEST_BAKERY_VERSION, AGES, None, ops)
        self.assertEquals(len(st._store), 1)
