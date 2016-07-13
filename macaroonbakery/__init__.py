# Copyright 2016 Canonical Ltd.
# Licensed under the AGPLv3, see LICENCE file for details.

from __future__ import unicode_literals
try:
    import urllib3.contrib.pyopenssl
    urllib3.contrib.pyopenssl.inject_into_urllib3()
except ImportError:
    pass

VERSION = (0, 0, 1)


def get_version():
    """Return the macaroon bakery version as a string."""
    return '.'.join(map(str, VERSION))
