# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
import json

import nacl.public
import nacl.encoding
import requests.cookies
import six
from six.moves.urllib.parse import urlparse


class AgentFileFormatError(Exception):
    """ AgentFileFormatError is the exception raised when an agent file has a bad
          structure.
    """
    pass


def load_agent_file(filename, cookies=None):
    """ Loads agent information from the specified file.

        The agent cookies are added to cookies, or a newly created cookie jar
        if cookies is not specified. The updated cookies is returned along
        with the private key associated with the agent. These can be passed
        directly as the cookies and key parameter to BakeryAuth.
    """

    with open(filename) as f:
        data = json.load(f)
    try:
        key = nacl.public.PrivateKey(data['key']['private'],
                                     nacl.encoding.Base64Encoder)
        if cookies is None:
            cookies = requests.cookies.RequestsCookieJar()
        for agent in data['agents']:
            u = urlparse(agent['url'])
            value = {'username': agent['username'],
                     'public_key': data['key']['public']}
            jv = json.dumps(value)
            if six.PY3:
                jv = jv.encode('utf-8')
            v = base64.b64encode(jv)
            if six.PY3:
                v = v.decode('utf-8')
            cookie = requests.cookies.create_cookie('agent-login', v,
                                                    domain=u.netloc,
                                                    path=u.path)
            cookies.set_cookie(cookie)
        return cookies, key
    except (KeyError, ValueError) as e:
        raise AgentFileFormatError("invalid agent file", e)
