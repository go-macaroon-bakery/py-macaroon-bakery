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

BAKERY_V0 = 0
BAKERY_V1 = 1
BAKERY_V2 = 2
BAKERY_V3 = 3
LATEST_BAKERY_VERSION = BAKERY_V3


def get_version():
    '''Return the macaroon bakery version as a string.'''
    return '.'.join(map(str, VERSION))

__all__ = [
    'VERSION', 'BAKERY_V0', 'BAKERY_V1', 'BAKERY_V2', 'BAKERY_V3',
    'LATEST_BAKERY_VERSION'
]
