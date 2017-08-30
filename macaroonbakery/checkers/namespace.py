# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import collections
import six

# StdNamespace holds the URI of the standard checkers schema.
STD_NAMESPACE = 'std'


class Namespace:
    '''Holds maps from schema URIs to prefixes.

    prefixes that are used to encode them in first party
    caveats. Several different URIs may map to the same
    prefix - this is usual when several different backwardly
    compatible schema versions are registered.
    '''
    def __init__(self, uri_to_prefix=None):
        self._uri_to_prefix = {}
        if uri_to_prefix is not None:
            for k in uri_to_prefix:
                self.register(k, uri_to_prefix[k])

    def __str__(self):
        '''Returns the namespace representation as returned by serialize
        :return: str
        '''
        return self.serialize().decode('utf-8')

    def __eq__(self, other):
        return self._uri_to_prefix == other._uri_to_prefix

    def serialize(self):
        '''Returns a serialize form of the Namepace.

        All the elements in the namespace are sorted by
        URI, joined to the associated prefix with a colon and
        separated with spaces.
        :return: bytes
        '''
        if self._uri_to_prefix is None or len(self._uri_to_prefix) == 0:
            return b''
        od = collections.OrderedDict(sorted(self._uri_to_prefix.items()))
        data = []
        for uri in od:
            data.append(uri + ':' + od[uri])
        return six.b(' '.join(data))

    def register(self, uri, prefix):
        '''Registers the given URI and associates it with the given prefix.

        If the URI has already been registered, this is a no-op.

        :param uri: string
        :param prefix: string
        '''
        if not is_valid_schema_uri(uri):
            raise KeyError(
                'cannot register invalid URI {} (prefix {})'.format(
                    uri, prefix))
        if not is_valid_prefix(prefix):
            raise ValueError(
                'cannot register invalid prefix %q for URI %q'.format(
                    prefix, uri))
        if self._uri_to_prefix.get(uri) is None:
            self._uri_to_prefix[uri] = prefix

    def resolve(self, uri):
        ''' Returns the prefix associated to the uri.

        returns None if not found.
        :param uri: string
        :return: string
        '''
        return self._uri_to_prefix.get(uri)


def is_valid_schema_uri(uri):
    '''Reports if uri is suitable for use as a namespace schema URI.

    It must be non-empty and it must not contain white space.

    :param uri string
    :return bool
    '''
    if len(uri) <= 0:
        return False
    return uri.find(' ') == -1


def is_valid_prefix(prefix):
    '''Reports if prefix is valid.

    It must not contain white space or semi-colon.
    :param prefix string
    :return bool
    '''
    return prefix.find(' ') == -1 and prefix.find(':') == -1


def deserialize_namespace(data):
    ''' Deserialize a Namespace object.

    :param data: bytes or str
    :return: namespace
    '''
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    kvs = data.split(' ')
    uri_to_prefix = {}
    for kv in kvs:
        k, v = kv.split(':')
        uri_to_prefix[k] = v
    return Namespace(uri_to_prefix)
