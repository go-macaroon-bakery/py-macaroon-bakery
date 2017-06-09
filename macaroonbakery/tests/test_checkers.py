# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from datetime import datetime, timedelta
from unittest import TestCase

import six
import pytz
from pymacaroons import Macaroon, MACAROON_V2

from macaroonbakery.auth_context import AuthContext
from macaroonbakery.checkers.checkers import (
    Checker, Namespace, CheckerInfo
)
from macaroonbakery.checkers import COND_DECLARED, COND_ALLOW, STD_NAMESPACE
from macaroonbakery.checkers.caveat import (
    time_before_caveat, deny_caveat, allow_caveat, declared_caveat, Caveat
)
from macaroonbakery.checkers.declared import (
    infer_declared,
    context_with_declared
)
from macaroonbakery.checkers.time import context_with_clock
from macaroonbakery.checkers.operation import context_with_operations

# A frozen time for the tests.
NOW = datetime(
    year=2006, month=1, day=2, hour=15, minute=4, second=5, microsecond=123)


class TestClock():
    def utcnow(self):
        return pytz.UTC.localize(NOW)


class TestCheckers(TestCase):
    def test_checkers(self):

        tests = [
            ('nothing in context, no extra checkers', [
                ('something',
                 'caveat "something" not satisfied: caveat not recognized'),
                ('', 'cannot parse caveat "": empty caveat'),
                (' hello', 'cannot parse caveat " hello": caveat starts with'
                           ' space character'),
            ], None),
            ('one failed caveat', [
                ('t:a aval', None),
                ('t:b bval', None),
                ('t:a wrong', 'caveat "t:a wrong" not satisfied: wrong arg'),
            ], None),
            ('time from clock', [
                (time_before_caveat(
                    datetime.utcnow() +
                    timedelta(0, 1)).condition,
                 None),
                (time_before_caveat(NOW).condition,
                 'caveat "time-before 2006-01-02T15:04:05.000123Z" '
                 'not satisfied: macaroon has expired'),
                (time_before_caveat(NOW - timedelta(0, 1)).condition,
                 'caveat "time-before 2006-01-02T15:04:04.000123Z" '
                 'not satisfied: macaroon has expired'),
                ('time-before bad-date',
                 'caveat "time-before bad-date" not satisfied: '
                 'cannot parse "bad-date" as RFC 3339'),
                (time_before_caveat(NOW).condition + " ",
                 'caveat "time-before 2006-01-02T15:04:05.000123Z " '
                 'not satisfied: '
                 'cannot parse "2006-01-02T15:04:05.000123Z " as RFC 3339'),
            ], lambda x: context_with_clock(ctx, TestClock())),
            ('real time', [
                (time_before_caveat(datetime(
                    year=2010, month=1, day=1)).condition,
                 'caveat "time-before 2010-01-01T00:00:00.000000Z" not '
                 'satisfied: macaroon has expired'),
                (time_before_caveat(datetime(
                    year=3000, month=1, day=1)).condition, None),
            ], None),
            ('declared, no entries', [
                (declared_caveat("a", "aval").condition,
                 'caveat "declared a aval" not satisfied: got a=null, '
                 'expected "aval"'),
                (COND_DECLARED, 'caveat "declared" not satisfied: '
                                'declared caveat has no value'),
            ], None),
            ('declared, some entries', [
                (declared_caveat("a", "aval").condition, None),
                (declared_caveat("b", "bval").condition, None),
                (declared_caveat("spc", " a b").condition, None),
                (declared_caveat("a", "bval").condition,
                 'caveat "declared a bval" not satisfied: '
                 'got a="aval", expected "bval"'),
                (declared_caveat("a", " aval").condition,
                 'caveat "declared a  aval" not satisfied: '
                 'got a="aval", expected " aval"'),
                (declared_caveat("spc", "a b").condition,
                 'caveat "declared spc a b" not satisfied: '
                 'got spc=" a b", expected "a b"'),
                (declared_caveat("", "a b").condition,
                 'caveat "error invalid caveat \'declared\' key """ '
                 'not satisfied: bad caveat'),
                (declared_caveat("a b", "a b").condition,
                 'caveat "error invalid caveat \'declared\' key "a b"" '
                 'not satisfied: bad caveat'),
            ], lambda x: context_with_declared(x, {
                'a': 'aval',
                'b': 'bval',
                'spc': ' a b'})),
        ]
        checker = Checker()
        checker.namespace().register('testns', 't')
        checker.register('a', 'testns', arg_checker(self, 't:a', 'aval'))
        checker.register('b', 'testns', arg_checker(self, 't:b', 'bval'))
        ctx = AuthContext()
        for test in tests:
            print(test[0])
            if test[2] is not None:
                ctx1 = test[2](ctx)
            else:
                ctx1 = ctx
            for check in test[1]:
                err = checker.check_first_party_caveat(ctx1, check[0])
                if check[1] is not None:
                    self.assertEqual(err, check[1])
                else:
                    self.assertIsNone(err)

    def test_infer_declared(self):
        tests = [
            ('no macaroons', [], {}, None),
            ('single macaroon with one declaration', [
                [Caveat(condition='declared foo bar')]
            ], {'foo': 'bar'}, None),
            ('only one argument to declared', [
                [Caveat(condition='declared foo')]
            ], {}, None),
            ('spaces in value', [
                [Caveat(condition='declared foo bar bloggs')]
            ], {'foo': 'bar bloggs'}, None),
            ('attribute with declared prefix', [
                [Caveat(condition='declaredccf foo')]
            ], {}, None),
            ('several macaroons with different declares', [
                [
                    declared_caveat('a', 'aval'),
                    declared_caveat('b', 'bval')
                ], [
                    declared_caveat('c', 'cval'),
                    declared_caveat('d', 'dval')
                ]
            ], {'a': 'aval', 'b': 'bval', 'c': 'cval', 'd': 'dval'}, None),
            ('duplicate values', [
                [
                    declared_caveat('a', 'aval'),
                    declared_caveat('a', 'aval'),
                    declared_caveat('b', 'bval')
                ], [
                    declared_caveat('a', 'aval'),
                    declared_caveat('b', 'bval'),
                    declared_caveat('c', 'cval'),
                    declared_caveat('d', 'dval')
                ]
            ], {'a': 'aval', 'b': 'bval', 'c': 'cval', 'd': 'dval'}, None),
            ('conflicting values', [
                [
                    declared_caveat('a', 'aval'),
                    declared_caveat('a', 'conflict'),
                    declared_caveat('b', 'bval')
                ], [
                    declared_caveat('a', 'conflict'),
                    declared_caveat('b', 'another conflict'),
                    declared_caveat('c', 'cval'),
                    declared_caveat('d', 'dval')
                ]
            ], {'c': 'cval', 'd': 'dval'}, None),
            ('third party caveats ignored', [
                [Caveat(condition='declared a no conflict',
                        location='location')],
                [declared_caveat('a', 'aval')]
            ], {'a': 'aval'}, None),
            ('unparseable caveats ignored', [
                [Caveat(condition=' bad')], [declared_caveat('a', 'aval')]
            ], {'a': 'aval'}, None),
            ('infer with namespace', [
                [
                    declared_caveat('a', 'aval'),
                    caveat_with_ns(declared_caveat('a', 'aval'), 'testns'),
                ]
            ], {'a': 'aval'}, None),
        ]
        for test in tests:
            uri_to_prefix = test[3]
            if uri_to_prefix is None:
                uri_to_prefix = {STD_NAMESPACE: ''}
            ns = Namespace(uri_to_prefix)
            print(test[0])
            ms = []
            for i, caveats in enumerate(test[1]):
                m = Macaroon(key=None, identifier=six.int2byte(i), location='',
                             version=MACAROON_V2)
                for cav in caveats:
                    cav = ns.resolve_caveat(cav)
                    if cav.location == '':
                        m.add_first_party_caveat(cav.condition)
                    else:
                        m.add_third_party_caveat(cav.location, None,
                                                 cav.condition)
                ms.append(m)
            self.assertEqual(infer_declared(ms), test[2])

    def test_operations_checker(self):
        tests = [
            ('all allowed', allow_caveat(['op1', 'op2', 'op4', 'op3']),
             ['op1', 'op3', 'op2'], None),
            ('none denied', deny_caveat(['op1', 'op2']),
             ['op3', 'op4'], None),
            ('one not allowed', allow_caveat(['op1', 'op2']),
             ['op1', 'op3'],
             'caveat "allow op1 op2" not satisfied: op3 not allowed'),
            ('one not denied', deny_caveat(['op1', 'op2']),
             ['op4', 'op5', 'op2'],
             'caveat "deny op1 op2" not satisfied: op2 not allowed'),
            ('no operations, allow caveat', allow_caveat(['op1']),
             [],
             'caveat "allow op1" not satisfied: op1 not allowed'),
            ('no operations, deny caveat', deny_caveat(['op1']),
             [], None),
            ('no operations, empty allow caveat', Caveat(condition=COND_ALLOW),
             [], 'caveat "allow" not satisfied: no operations allowed'),
        ]
        checker = Checker()
        for test in tests:
            print(test[0])
            ctx = context_with_operations(AuthContext(), test[2])
            err = checker.check_first_party_caveat(ctx, test[1].condition)
            if test[3] is None:
                self.assertIsNone(err)
                continue
            self.assertEqual(err, test[3])

    def test_operation_error_caveat(self):
        tests = [
            ('empty allow', allow_caveat(None), 'error no operations allowed'),
            ('allow: invalid operation name',
             allow_caveat(['op1', 'operation number 2']),
             'error invalid operation name "operation number 2"'),
            ('deny: invalid operation name',
             deny_caveat(['op1', 'operation number 2']),
             'error invalid operation name "operation number 2"')
        ]
        for test in tests:
            print(test[0])
            self.assertEqual(test[1].condition, test[2])

    def test_register_none_func_raise_exception(self):
        checker = Checker()
        with self.assertRaises(ValueError) as ctx:
            checker.register('x', STD_NAMESPACE, None)
        self.assertEqual(ctx.exception.args[0],
                         'no check function registered for namespace std when '
                         'registering condition x')

    def test_register_no_registered_ns_exception(self):
        checker = Checker()
        with self.assertRaises(ValueError) as ctx:
            checker.register('x', 'testns', lambda x: None)
        self.assertEqual(ctx.exception.args[0],
                         'no prefix registered for namespace testns when '
                         'registering condition x')

    def test_register_empty_prefix_condition_with_colon(self):
        checker = Checker()
        checker.namespace().register('testns', '')
        with self.assertRaises(ValueError) as ctx:
            checker.register('x:y', 'testns', lambda x: None)
        self.assertEqual(ctx.exception.args[0],
                         'caveat condition x:y in namespace testns contains a '
                         'colon but its prefix is empty')

    def test_register_twice_same_namespace(self):
        checker = Checker()
        checker.namespace().register('testns', '')
        checker.register('x', 'testns', lambda x: None)
        with self.assertRaises(ValueError) as ctx:
            checker.register('x', 'testns', lambda x: None)
        self.assertEqual(ctx.exception.args[0],
                         'checker for x (namespace testns) already registered'
                         ' in namespace testns')

    def test_register_twice_different_namespace(self):
        checker = Checker()
        checker.namespace().register('testns', '')
        checker.namespace().register('otherns', '')
        checker.register('x', 'testns', lambda x: None)
        with self.assertRaises(ValueError) as ctx:
            checker.register('x', 'otherns', lambda x: None)
        self.assertEqual(ctx.exception.args[0],
                         'checker for x (namespace otherns) already registered'
                         ' in namespace testns')

    def test_checker_info(self):
        checker = Checker(include_std_checkers=False)
        checker.namespace().register('one', 't')
        checker.namespace().register('two', 't')
        checker.namespace().register('three', '')
        checker.namespace().register('four', 's')

        class Called(object):
            val = ''

        def register(name, ns):
            def func(ctx, cond, arg):
                Called.val = name + ' ' + ns
                return None

            checker.register(name, ns, func)

        register('x', 'one')
        register('y', 'one')
        register('z', 'two')
        register('a', 'two')
        register('something', 'three')
        register('other', 'three')
        register('xxx', 'four')

        expect = [
            CheckerInfo(ns='four', name='xxx', prefix='s'),
            CheckerInfo(ns='one', name='x', prefix='t'),
            CheckerInfo(ns='one', name='y', prefix='t'),
            CheckerInfo(ns='three', name='other', prefix=''),
            CheckerInfo(ns='three', name='something', prefix=''),
            CheckerInfo(ns='two', name='a', prefix='t'),
            CheckerInfo(ns='two', name='z', prefix='t'),
        ]
        infos = checker.info()
        self.assertEqual(len(infos), len(expect))
        for i, info in enumerate(infos):
            Called.val = ''
            info.check(None, '', '')
            self.assertEqual(Called.val, expect[i].name + ' '
                             + expect[i].ns)
        self.assertEqual(infos, expect)


def caveat_with_ns(cav, ns):
    return Caveat(location=cav.location, condition=cav.condition, namespace=ns)


def arg_checker(test, expect_cond, check_arg):
    ''' Returns a checker function that checks that the caveat condition is
    check_arg.
    '''

    def func(ctx, cond, arg):
        test.assertEqual(cond, expect_cond)
        if arg != check_arg:
            return 'wrong arg'
        return None

    return func
