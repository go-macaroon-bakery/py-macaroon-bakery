# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import os


class MemoryOpsStore:
    ''' A multi-op store that stores the operations in memory.
    '''
    def __init__(self):
        self._store = {}

    def put_ops(self, key, time, *ops):
        ''' Put an ops only if not already there, otherwise it's a no op.
        '''
        if self._store.get(key) is None:
            self._store[key] = ops

    def get_ops(self, key):
        ''' Returns ops from the key if found otherwise raises a KeyError.
        '''
        ops = self._store.get(key)
        if ops is None:
            raise KeyError(
                'cannot get operations for {}'.format(key))
        return ops


class MemoryKeyStore:
    ''' MemoryKeyStore returns an implementation of
    Store that generates a single key and always
    returns that from root_key. The same id ("0") is always
    used.
    '''
    def __init__(self):
        self.key = None

    def get(self, id):
        if len(id) != 1 or id[:1] != b'0' or self.key is None:
            return None
        return self.key

    def root_key(self):
        if self.key is None:
            self.key = os.urandom(24)
        return self.key, b'0'
