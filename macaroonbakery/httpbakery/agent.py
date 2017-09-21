# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import base64
from collections import namedtuple
import json

import nacl.public
import nacl.encoding
import requests.cookies
import six
from six.moves.urllib.parse import urlparse
from six.moves.urllib.parse import urljoin
from six.moves.http_cookiejar import Cookie

import macaroonbakery
from macaroonbakery import utils
from macaroonbakery.httpbakery.interactor import (
    Interactor, LegacyInteractor, DischargeToken
)
from macaroonbakery.httpbakery.error import (
    InteractionMethodNotFound, InteractionError
)
from macaroonbakery.httpbakery.client import BakeryAuth


class AgentFileFormatError(Exception):
    ''' AgentFileFormatError is the exception raised when an agent file has a
        bad structure.
    '''
    pass


def load_agent_file(filename, cookies=None):
    ''' Loads agent information from the specified file.

        The agent cookies are added to cookies, or a newly created cookie jar
        if cookies is not specified. The updated cookies is returned along
        with the private key associated with the agent. These can be passed
        directly as the cookies and key parameter to BakeryAuth.
    '''

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
        raise AgentFileFormatError('invalid agent file', e)


class InteractionInfo(object):
    '''Holds the information expected in the agent interaction entry in an
    interaction-required error.
    '''
    def __init__(self, login_url):
        self._login_url = login_url

    @property
    def login_url(self):
        ''' Return the URL from which to acquire a macaroon that can be used
        to complete the agent login. To acquire the macaroon, make a POST
        request to the URL with user and public-key parameters.
        :return string
        '''
        return self._login_url

    @classmethod
    def deserialize(cls, info_dict):
        return InteractionInfo(info_dict.get('login-url'))


class AgentInteractor(Interactor, LegacyInteractor):
    ''' Interactor that performs interaction using the agent login protocol.
    '''
    def __init__(self, auth_info):
        self._auth_info = auth_info

    def kind(self):
        return 'agent'

    def interact(self, ctx, location, interaction_required_err):
        p = interaction_required_err.interaction_method('agent',
                                                        InteractionInfo)
        if p.login_url is None or p.login_url == '':
            raise InteractionError(
                'no login-url field found in agent interaction method')
        agent = self.find_agent(location)
        if not location.endswith('/'):
            location += '/'
        login_url = urljoin(location, p.login_url)
        resp = requests.get(login_url, json={
            'Username': agent.username,
            'PublicKey': self._auth_info.key.encode().decode('utf-8'),
        })
        if resp.status_code != 200:
            raise InteractionError(
                'cannot acquire agent macaroon: {}'.format(resp.status_code)
            )
        m = resp.json().get('macaroon')
        if m is None:
            raise InteractionError('no macaroon in response')
        m = macaroonbakery.Macaroon.from_dict(m)
        ms = macaroonbakery.discharge_all(ctx, m, None, self._auth_info.key)
        b = bytearray()
        for m in ms:
            b.extend(utils.raw_b64decode(m.serialize()))
        return DischargeToken(kind='agent', value=bytes(b))

    def find_agent(self, location):
        ''' Finds an appropriate agent entry for the given location.
        :return Agent
        '''
        for a in self._auth_info.agents:
            # Don't worry about trailing slashes
            if a.url.rstrip('/') == location.rstrip('/'):
                return a
        raise InteractionMethodNotFound(
            'cannot find username for discharge location {}'.format(location))

    def legacy_interact(self, ctx, location, visit_url):
        agent = self.find_agent(location)
        pk_encoded = self._auth_info.key.public_key.encode().decode('utf-8')
        value = {
            'username': agent.username,
            'public_key': pk_encoded,
        }
        jar = requests.cookies.RequestsCookieJar()
        parsed_url = urlparse(visit_url)
        domain = parsed_url.hostname or parsed_url.netloc
        port = str(parsed_url.port) if parsed_url.port is not None else None
        secure = parsed_url.scheme == 'https'
        cookie = Cookie(
            version=0,
            name='agent-login',
            value=base64.urlsafe_b64encode(
                json.dumps(value).encode('utf-8')).decode('utf-8'),
            port=port,
            port_specified=port is not None,
            domain=domain,
            domain_specified=True,
            domain_initial_dot=False,
            path='/',
            path_specified=True,
            secure=secure,
            expires=None,
            discard=False,
            comment=None,
            comment_url=None,
            rest=None,
            rfc2109=False)
        jar.set_cookie(cookie)
        resp = requests.get(
            url=visit_url, cookies=jar,
            auth=BakeryAuth(
                key=self._auth_info.key,
                interaction_methods=self
            )
        )
        if resp.status_code != 200:
            raise InteractionError(
                'cannot acquire agent macaroon: {}'.format(resp.status_code))
        if not resp.json().get('agent-login', False):
            raise InteractionError('agent login failed')


class Agent(namedtuple('Agent', 'url, username')):
    ''' Represents an agent that can be used for agent authentication.
    @param url holds the URL associated with the agent.
    @param username holds the username to use for the agent.
    '''


class AuthInfo(namedtuple('AuthInfo', 'key, agents')):
    ''' Holds the agent information required to set up agent authentication
    information.

    It holds the agent's private key and information about the username
    associated with each known agent-authentication server.
    @param key the agent's private key.
    @param agents information about the username associated with each
    known agent-authentication server.
    '''
