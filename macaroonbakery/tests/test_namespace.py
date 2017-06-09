# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

from unittest import TestCase

from macaroonbakery import namespace


class TestNamespace(TestCase):
    def test_serialize(self):
        tests = [
            ('empty namespace', None, b''),
            ('standard namespace', {'std': ''}, b'std:'),
            ('several elements', {
                'std': '',
                'http://blah.blah': 'blah',
                'one': 'two',
                'foo.com/x.v0.1': 'z',
            }, b'foo.com/x.v0.1:z http://blah.blah:blah one:two std:'),
            ('sort by URI not by field', {
                'a': 'one',
                'a1': 'two',
            }, b'a:one a1:two')
        ]
        for test in tests:
            ns = namespace.Namespace(test[1])
            data = ns.serialize()
            self.assertEquals(data, test[2])
            self.assertEquals(str(ns), test[2].decode('utf-8'))

        # Check that it can be deserialize to the same thing:
        ns1 = namespace.deserialize_namespace(data)
        self.assertEquals(ns1, ns)

    def test_register(self):
        ns = namespace.Namespace(None)
        ns.register('testns', 't')
        prefix = ns.resolve('testns')
        self.assertEquals(prefix, 't')

        ns.register('other', 'o')
        prefix = ns.resolve('other')
        self.assertEquals(prefix, 'o')

        # If we re-register the same URL, it does nothing.
        ns.register('other', 'p')
        prefix = ns.resolve('other')
        self.assertEquals(prefix, 'o')

    def test_register_bad_uri(self):
        ns = namespace.Namespace(None)
        with self.assertRaises(KeyError):
            ns.register('', 'x')

    def test_register_bad_prefix(self):
        ns = namespace.Namespace(None)
        with self.assertRaises(ValueError):
            ns.register('std', 'x:1')
