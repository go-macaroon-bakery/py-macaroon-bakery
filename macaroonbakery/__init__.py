# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

from __future__ import unicode_literals
try:
    import urllib3.contrib.pyopenssl
except ImportError:
    pass
else:
    urllib3.contrib.pyopenssl.inject_into_urllib3()

VERSION = (0, 0, 3)


def get_version():
    '''Return the macaroon bakery version as a string.'''
    return '.'.join(map(str, VERSION))
