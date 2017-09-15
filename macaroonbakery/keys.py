# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from nacl.public import PrivateKey


def generate_key():
    '''GenerateKey generates a new key pair.
    :return: a nacl.public.PrivateKey
    '''
    return PrivateKey.generate()
