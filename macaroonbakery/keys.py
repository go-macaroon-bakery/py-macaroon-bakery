from nacl.public import PrivateKey


def generate_key():
    '''GenerateKey generates a new key pair.
    :return: a nacl.public.PrivateKey
    '''
    return PrivateKey.generate()
