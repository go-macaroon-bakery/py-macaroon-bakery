# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import unittest

from pymacaroons.verifier import Verifier

import macaroonbakery
import macaroonbakery.checkers as checkers
from macaroonbakery.tests import common


def always_ok(predicate):
    return True


class TestDischargeAll(unittest.TestCase):
    def test_discharge_all_no_discharges(self):
        root_key = b'root key'
        m = macaroonbakery.Macaroon(
            root_key=root_key, id=b'id0', location='loc0',
            version=macaroonbakery.LATEST_BAKERY_VERSION,
            namespace=common.test_checker().namespace())
        ms = macaroonbakery.discharge_all(
            common.test_context, m, no_discharge(self))
        self.assertEqual(len(ms), 1)
        self.assertEqual(ms[0], m.macaroon)
        v = Verifier()
        v.satisfy_general(always_ok)
        v.verify(m.macaroon, root_key, None)

    def test_discharge_all_many_discharges(self):
        root_key = b'root key'
        m0 = macaroonbakery.Macaroon(
            root_key=root_key, id=b'id0', location='loc0',
            version=macaroonbakery.LATEST_BAKERY_VERSION)

        class State(object):
            total_required = 40
            id = 1

        def add_caveats(m):
            for i in range(0, 1):
                if State.total_required == 0:
                    break
                cid = 'id{}'.format(State.id)
                m.macaroon.add_third_party_caveat(
                    location='somewhere',
                    key='root key {}'.format(cid).encode('utf-8'),
                    key_id=cid.encode('utf-8'))
                State.id += 1
                State.total_required -= 1

        add_caveats(m0)

        def get_discharge(_, cav, payload):
            self.assertEqual(payload, None)
            m = macaroonbakery.Macaroon(
                root_key='root key {}'.format(
                    cav.caveat_id.decode('utf-8')).encode('utf-8'),
                id=cav.caveat_id, location='',
                version=macaroonbakery.LATEST_BAKERY_VERSION)

            add_caveats(m)
            return m

        ms = macaroonbakery.discharge_all(
            common.test_context, m0, get_discharge)

        self.assertEqual(len(ms), 41)

        v = Verifier()
        v.satisfy_general(always_ok)
        v.verify(ms[0], root_key, ms[1:])

    def test_discharge_all_many_discharges_with_real_third_party_caveats(self):
        # This is the same flow as TestDischargeAllManyDischarges except that
        # we're using actual third party caveats as added by
        # Macaroon.add_caveat and we use a larger number of caveats
        # so that caveat ids will need to get larger.
        locator = macaroonbakery.ThirdPartyStore()
        bakeries = {}
        total_discharges_required = 40

        class M:
            bakery_id = 0
            still_required = total_discharges_required

        def add_bakery():
            M.bakery_id += 1
            loc = 'loc{}'.format(M.bakery_id)
            bakeries[loc] = common.new_bakery(loc, locator)
            return loc

        ts = common.new_bakery('ts-loc', locator)

        def checker(_, ci):
            caveats = []
            if ci.condition != 'something':
                self.fail('unexpected condition')
            for i in range(0, 2):
                if M.still_required <= 0:
                    break
                caveats.append(checkers.Caveat(location=add_bakery(),
                                               condition='something'))
                M.still_required -= 1
            return caveats

        root_key = b'root key'
        m0 = macaroonbakery.Macaroon(
            root_key=root_key, id=b'id0', location='ts-loc',
            version=macaroonbakery.LATEST_BAKERY_VERSION)

        m0.add_caveat(checkers. Caveat(location=add_bakery(),
                                       condition='something'),
                      ts.oven.key, locator)

        # We've added a caveat (the first) so one less caveat is required.
        M.still_required -= 1

        class ThirdPartyCaveatCheckerF(macaroonbakery.ThirdPartyCaveatChecker):
            def check_third_party_caveat(self, ctx, info):
                return checker(ctx, info)

        def get_discharge(ctx, cav, payload):
            return macaroonbakery.discharge(
                ctx, cav.caveat_id, payload,
                bakeries[cav.location].oven.key,
                ThirdPartyCaveatCheckerF(), locator)

        ms = macaroonbakery.discharge_all(common.test_context, m0,
                                          get_discharge)

        self.assertEqual(len(ms), total_discharges_required + 1)

        v = Verifier()
        v.satisfy_general(always_ok)
        v.verify(ms[0], root_key, ms[1:])

    def test_discharge_all_local_discharge(self):
        oc = common.new_bakery('ts', None)
        client_key = macaroonbakery.generate_key()
        m = oc.oven.macaroon(macaroonbakery.LATEST_BAKERY_VERSION, common.ages,
                             [
                                 macaroonbakery.local_third_party_caveat(
                                     client_key.public_key,
                                     macaroonbakery.LATEST_BAKERY_VERSION)
                             ], [macaroonbakery.LOGIN_OP])
        ms = macaroonbakery.discharge_all(
            common.test_context, m, no_discharge(self), client_key)
        oc.checker.auth([ms]).allow(common.test_context,
                                    [macaroonbakery.LOGIN_OP])

    def test_discharge_all_local_discharge_version1(self):
        oc = common.new_bakery('ts', None)
        client_key = macaroonbakery.generate_key()
        m = oc.oven.macaroon(macaroonbakery.BAKERY_V1, common.ages, [
            macaroonbakery.local_third_party_caveat(
                client_key.public_key, macaroonbakery.BAKERY_V1)
        ], [macaroonbakery.LOGIN_OP])
        ms = macaroonbakery.discharge_all(
            common.test_context, m, no_discharge(self), client_key)
        oc.checker.auth([ms]).allow(common.test_context,
                                    [macaroonbakery.LOGIN_OP])


def no_discharge(test):
    def get_discharge(ctx, cav, payload):
        test.fail("get_discharge called unexpectedly")

    return get_discharge
