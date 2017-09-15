# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import unittest

from pymacaroons import MACAROON_V1, Macaroon
from pymacaroons.exceptions import MacaroonInvalidSignatureException

from macaroonbakery import LATEST_BAKERY_VERSION, BAKERY_V1
from macaroonbakery.bakery import Bakery
from macaroonbakery.checker import LOGIN_OP
from macaroonbakery.checkers import (
    Caveat, need_declared_caveat, infer_declared, context_with_declared,
    declared_caveat
)
from macaroonbakery.macaroon import ThirdPartyStore
from macaroonbakery.store import MemoryKeyStore
from macaroonbakery.tests import common
from macaroonbakery.discharge import (
    discharge, discharge_all, ThirdPartyCaveatChecker
)
from macaroonbakery.error import AuthInitError


class TestDischarge(unittest.TestCase):

    def test_single_service_first_party(self):
        ''' Creates a single service with a macaroon with one first party
        caveat.
        It creates a request with this macaroon and checks that the service
        can verify this macaroon as valid.
        '''
        oc = common.new_bakery('bakerytest')
        primary = oc.oven.macaroon(LATEST_BAKERY_VERSION,
                                   common.ages, None, LOGIN_OP)
        self.assertEqual(primary.macaroon.location, 'bakerytest')
        primary.add_caveat(Caveat(condition='str something',
                                  namespace='testns'),
                           oc.oven.key, oc.oven.locator)
        oc.checker.auth([primary.macaroon]).allow(
            common.str_context('something'), LOGIN_OP)

    def test_macaroon_paper_fig6(self):
        ''' Implements an example flow as described in the macaroons paper:
        http://theory.stanford.edu/~ataly/Papers/macaroons.pdf
        There are three services, ts, fs, bs:
        ts is a store service which has deligated authority to a forum
        service fs.
        The forum service wants to require its users to be logged into to an
        authentication service bs.

        The client obtains a macaroon from fs (minted by ts, with a third party
         caveat addressed to bs).
        The client obtains a discharge macaroon from bs to satisfy this caveat.
        The target service verifies the original macaroon it delegated to fs
        No direct contact between bs and ts is required
        '''
        locator = ThirdPartyStore()
        bs = common.new_bakery('bs-loc', locator)
        ts = common.new_bakery('ts-loc', locator)
        fs = common.new_bakery('fs-loc', locator)

        # ts creates a macaroon.
        ts_macaroon = ts.oven.macaroon(LATEST_BAKERY_VERSION, common.ages,
                                       None, LOGIN_OP)

        # ts somehow sends the macaroon to fs which adds a third party caveat
        # to be discharged by bs.
        ts_macaroon.add_caveat(Caveat(location='bs-loc',
                                      condition='user==bob'),
                               fs.oven.key, fs.oven.locator)

        # client asks for a discharge macaroon for each third party caveat
        def get_discharge(ctx, cav, payload):
            self.assertEqual(cav.location, 'bs-loc')
            return discharge(ctx, cav.caveat_id_bytes, payload, bs.oven.key,
                             common.ThirdPartyStrcmpChecker('user==bob'),
                             bs.oven.locator)

        d = discharge_all(common.test_context, ts_macaroon, get_discharge)

        ts.checker.auth(d).allow(common.test_context, LOGIN_OP)

    def test_discharge_with_version1_macaroon(self):
        locator = ThirdPartyStore()
        bs = common.new_bakery('bs-loc', locator)
        ts = common.new_bakery('ts-loc', locator)

        # ts creates a old-version macaroon.
        ts_macaroon = ts.oven.macaroon(BAKERY_V1, common.ages, None, LOGIN_OP)
        ts_macaroon.add_caveat(Caveat(condition='something',
                                      location='bs-loc'),
                               ts.oven.key, ts.oven.locator)
        # client asks for a discharge macaroon for each third party caveat

        def get_discharge(ctx, cav, payload):
            # Make sure that the caveat id really is old-style.
            try:
                cav.caveat_id_bytes.decode('utf-8')
            except UnicodeDecodeError:
                self.fail('caveat id is not utf-8')
            return discharge(ctx, cav.caveat_id_bytes, payload, bs.oven.key,
                             common.ThirdPartyStrcmpChecker('something'),
                             bs.oven.locator)
        d = discharge_all(common.test_context, ts_macaroon, get_discharge)

        ts.checker.auth(d).allow(common.test_context, LOGIN_OP)

        for m in d:
            self.assertEqual(m.version, MACAROON_V1)

    def test_version1_macaroon_id(self):
        # In the version 1 bakery, macaroon ids were hex-encoded with a
        # hyphenated UUID suffix.
        root_key_store = MemoryKeyStore()
        b = Bakery(root_key_store=root_key_store,
                   identity_client=common.OneIdentity())
        key, id = root_key_store.root_key()
        root_key_store.get(id)
        m = Macaroon(key=key, version=MACAROON_V1, location='',
                     identifier=id + b'-deadl00f')
        b.checker.auth(*[[m]]).allow(common.test_context, LOGIN_OP)

    @unittest.skip('waiting for fix on pymacaroons')
    def test_macaroon_paper_fig6_fails_without_discharges(self):
        ''' Runs a similar test as test_macaroon_paper_fig6 without the client
        discharging the third party caveats.
        '''
        locator = ThirdPartyStore()
        ts = common.new_bakery('ts-loc', locator)
        fs = common.new_bakery('fs-loc', locator)
        common.new_bakery('as-loc', locator)

        # ts creates a macaroon.
        ts_macaroon = ts.oven.macaroon(LATEST_BAKERY_VERSION,
                                       common.ages, None, LOGIN_OP)

        # ts somehow sends the macaroon to fs which adds a third party
        # caveat to be discharged by as.
        ts_macaroon.add_caveat(Caveat(location='as-loc',
                                      condition='user==bob'),
                               fs.oven.key, fs.oven.locator)

        # client makes request to ts
        ts.checker.auth([ts_macaroon.macaroon]).allow(common.test_context,
                                                      LOGIN_OP)

    def test_macaroon_paper_fig6_fails_with_binding_on_tampered_sig(self):
        ''' Runs a similar test as test_macaroon_paper_fig6 with the discharge
        macaroon binding being done on a tampered signature.
        '''
        locator = ThirdPartyStore()
        bs = common.new_bakery('bs-loc', locator)
        ts = common.new_bakery('ts-loc', locator)

        # ts creates a macaroon.
        ts_macaroon = ts.oven.macaroon(LATEST_BAKERY_VERSION,
                                       common.ages, None, LOGIN_OP)
        # ts somehow sends the macaroon to fs which adds a third party caveat
        # to be discharged by as.
        ts_macaroon.add_caveat(Caveat(condition='user==bob',
                                      location='bs-loc'),
                               ts.oven.key, ts.oven.locator)

        # client asks for a discharge macaroon for each third party caveat
        def get_discharge(ctx, cav, payload):
            self.assertEqual(cav.location, 'bs-loc')
            return discharge(ctx, cav.caveat_id_bytes, payload, bs.oven.key,
                             common.ThirdPartyStrcmpChecker('user==bob'),
                             bs.oven.locator)
        d = discharge_all(common.test_context, ts_macaroon, get_discharge)
        # client has all the discharge macaroons. For each discharge macaroon
        # bind it to our ts_macaroon and add it to our request.
        tampered_macaroon = Macaroon()
        for i, dm in enumerate(d[1:]):
            d[i+1] = tampered_macaroon.prepare_for_request(dm)

        # client makes request to ts.
        with self.assertRaises(MacaroonInvalidSignatureException) as exc:
            ts.checker.auth(d).allow(common.test_context, LOGIN_OP)
        self.assertEqual('Signatures do not match.', exc.exception.args[0])

    def test_need_declared(self):
        locator = ThirdPartyStore()
        first_party = common.new_bakery('first', locator)
        third_party = common.new_bakery('third', locator)

        # firstParty mints a macaroon with a third-party caveat addressed
        # to thirdParty with a need-declared caveat.
        m = first_party.oven.macaroon(
            LATEST_BAKERY_VERSION, common.ages, [
                need_declared_caveat(Caveat(location='third',
                                            condition='something'),
                                     ['foo', 'bar'])
            ], LOGIN_OP)

        # The client asks for a discharge macaroon for each third party caveat.
        def get_discharge(ctx, cav, payload):
            return discharge(ctx, cav.caveat_id_bytes, payload,
                             third_party.oven.key,
                             common.ThirdPartyStrcmpChecker('something'),
                             third_party.oven.locator)
        d = discharge_all(common.test_context, m, get_discharge)

        # The required declared attributes should have been added
        # to the discharge macaroons.
        declared = infer_declared(d, first_party.checker.namespace())
        self.assertEqual(declared, {
            'foo': '',
            'bar': '',
        })

        # Make sure the macaroons actually check out correctly
        # when provided with the declared checker.
        ctx = context_with_declared(common.test_context, declared)
        first_party.checker.auth(d).allow(ctx, LOGIN_OP)

        # Try again when the third party does add a required declaration.

        # The client asks for a discharge macaroon for each third party caveat.
        def get_discharge(ctx, cav, payload):
            checker = common.ThirdPartyCheckerWithCaveats([
                declared_caveat('foo', 'a'),
                declared_caveat('arble', 'b')
            ])
            return discharge(ctx, cav.caveat_id_bytes, payload,
                             third_party.oven.key,
                             checker,
                             third_party.oven.locator)
        d = discharge_all(common.test_context, m, get_discharge)

        # One attribute should have been added, the other was already there.
        declared = infer_declared(d, first_party.checker.namespace())
        self.assertEqual(declared, {
            'foo':   'a',
            'bar':   '',
            'arble': 'b',
        })

        ctx = context_with_declared(common.test_context, declared)
        first_party.checker.auth(d).allow(ctx, LOGIN_OP)

        # Try again, but this time pretend a client is sneakily trying
        # to add another 'declared' attribute to alter the declarations.

        def get_discharge(ctx, cav, payload):
            checker = common.ThirdPartyCheckerWithCaveats([
                declared_caveat('foo', 'a'),
                declared_caveat('arble', 'b'),
            ])

            # Sneaky client adds a first party caveat.
            m = discharge(ctx, cav.caveat_id_bytes, payload,
                          third_party.oven.key, checker,
                          third_party.oven.locator)
            m.add_caveat(declared_caveat('foo', 'c'), None, None)
            return m
        d = discharge_all(common.test_context, m, get_discharge)

        declared = infer_declared(d, first_party.checker.namespace())
        self.assertEqual(declared, {
            'bar':   '',
            'arble': 'b',
        })

        with self.assertRaises(AuthInitError) as exc:
            first_party.checker.auth(d).allow(common.test_context, LOGIN_OP)
        self.assertEqual('cannot authorize login macaroon: caveat '
                         '"declared foo a" not satisfied: got foo=null, '
                         'expected "a"', exc.exception.args[0])

    def test_discharge_two_need_declared(self):
        locator = ThirdPartyStore()
        first_party = common.new_bakery('first', locator)
        third_party = common.new_bakery('third', locator)

        # first_party mints a macaroon with two third party caveats
        # with overlapping attributes.
        m = first_party.oven.macaroon(LATEST_BAKERY_VERSION, common.ages, [
            need_declared_caveat(Caveat(location='third', condition='x'),
                                 ['foo', 'bar']),
            need_declared_caveat(Caveat(location='third', condition='y'),
                                 ['bar', 'baz']),
        ], LOGIN_OP)

        # The client asks for a discharge macaroon for each third party caveat.
        # Since no declarations are added by the discharger,

        def get_discharge(ctx, cav, payload):
            return discharge(ctx, cav.caveat_id_bytes, payload,
                             third_party.oven.key,
                             common.ThirdPartyCaveatCheckerEmpty(),
                             third_party.oven.locator)

        d = discharge_all(common.test_context, m, get_discharge)
        declared = infer_declared(d, first_party.checker.namespace())
        self.assertEqual(declared, {
            'foo': '',
            'bar': '',
            'baz': '',
        })
        ctx = context_with_declared(common.test_context, declared)
        first_party.checker.auth(d).allow(ctx, LOGIN_OP)

        # If they return conflicting values, the discharge fails.
        # The client asks for a discharge macaroon for each third party caveat.
        # Since no declarations are added by the discharger,
        class ThirdPartyCaveatCheckerF(ThirdPartyCaveatChecker):
            def check_third_party_caveat(self, ctx, cav_info):
                if cav_info.condition == b'x':
                    return [declared_caveat('foo', 'fooval1')]
                if cav_info.condition == b'y':
                    return [
                        declared_caveat('foo', 'fooval2'),
                        declared_caveat('baz', 'bazval')
                    ]
                raise common.ThirdPartyCaveatCheckFailed('not matched')

        def get_discharge(ctx, cav, payload):
            return discharge(ctx, cav.caveat_id_bytes, payload,
                             third_party.oven.key,
                             ThirdPartyCaveatCheckerF(),
                             third_party.oven.locator)
        d = discharge_all(common.test_context, m, get_discharge)

        declared = infer_declared(d, first_party.checker.namespace())
        self.assertEqual(declared, {
            'bar': '',
            'baz': 'bazval',
        })
        ctx = context_with_declared(common.test_context, declared)
        with self.assertRaises(AuthInitError) as exc:
            first_party.checker.auth(d).allow(common.test_context, LOGIN_OP)
        self.assertEqual('cannot authorize login macaroon: caveat "declared '
                         'foo fooval1" not satisfied: got foo=null, expected '
                         '"fooval1"', exc.exception.args[0])

    def test_discharge_macaroon_cannot_be_used_as_normal_macaroon(self):
        locator = ThirdPartyStore()
        first_party = common.new_bakery('first', locator)
        third_party = common.new_bakery('third', locator)

        # First party mints a macaroon with a 3rd party caveat.
        m = first_party.oven.macaroon(LATEST_BAKERY_VERSION, common.ages, [
            Caveat(location='third', condition='true')], LOGIN_OP)

        # Acquire the discharge macaroon, but don't bind it to the original.
        class M:
            unbound = None

        def get_discharge(ctx, cav, payload):
            m = discharge(ctx, cav.caveat_id_bytes, payload,
                          third_party.oven.key,
                          common.ThirdPartyStrcmpChecker('true'),
                          third_party.oven.locator)
            M.unbound = m.macaroon.copy()
            return m
        discharge_all(common.test_context, m, get_discharge)
        self.assertIsNotNone(M.unbound)

        # Make sure it cannot be used as a normal macaroon in the third party.
        with self.assertRaises(ValueError) as exc:
            third_party.checker.auth([M.unbound]).allow(common.test_context,
                                                        LOGIN_OP)
        self.assertEqual('no operations found in macaroon',
                         exc.exception.args[0])

    @unittest.skip('waiting for fix on pymacaroons')
    def test_third_party_discharge_macaroon_ids_are_small(self):
        locator = ThirdPartyStore()
        bakeries = {
            'ts-loc':  common.new_bakery('ts-loc', locator),
            'as1-loc': common.new_bakery('as1-loc', locator),
            'as2-loc': common.new_bakery('as2-loc', locator),
        }
        ts = bakeries['ts-loc']

        ts_macaroon = ts.oven.macaroon(LATEST_BAKERY_VERSION, common.ages,
                                       None, LOGIN_OP)
        ts_macaroon.add_caveat(Caveat(condition='something',
                                      location='as1-loc'),
                               ts.oven.key, ts.oven.locator)

        class ThirdPartyCaveatCheckerF(common.ThirdPartyCaveatChecker):
            def __init__(self, loc):
                self._loc = loc

            def check_third_party_caveat(self, ctx, info):
                if self._loc == 'as1-loc':
                    return [Caveat(condition='something', location='as2-loc')]
                if self._loc == 'as2-loc':
                    return []
                raise common.ThirdPartyCaveatCheckFailed(
                    'unknown location {}'.format(self._loc))

        def get_discharge(ctx, cav, payload):
            oven = bakeries[cav.location].oven
            return discharge(ctx, cav.caveat_id_bytes, payload, oven.key,
                             ThirdPartyCaveatCheckerF(cav.location),
                             oven.locator)

        d = discharge_all(common.test_context, ts_macaroon, get_discharge)
        ts.checker.auth(d).allow(common.test_context, LOGIN_OP)

        for i, m in enumerate(d):
            for j, cav in enumerate(m.caveats()):
                if cav.VerificationId is not None and len(cav.id) > 3:
                    self.fail('caveat id on caveat {} of macaroon {} '
                              'is too big ({})'.format(j, i, cav.id))
