# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import base64
from collections import namedtuple
import json

import nacl.public
import nacl.encoding
import nacl.exceptions
import requests.cookies
import six
from six.moves.urllib.parse import urlparse
from six.moves.urllib.parse import urljoin

import macaroonbakery as bakery
import macaroonbakery.utils as utils
import macaroonbakery.httpbakery as httpbakery


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
        key = nacl.public.PrivateKey(
            data['key']['private'],
            nacl.encoding.Base64Encoder,
        )
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
    except (KeyError, ValueError, nacl.exceptions.TypeError) as e:
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
    def from_dict(cls, json_dict):
        '''Return an InteractionInfo obtained from the given dictionary as
        deserialized from JSON.
        @param json_dict The deserialized JSON object.
        '''
        return InteractionInfo(json_dict.get('login-url'))


class AgentInteractor(httpbakery.Interactor, httpbakery.LegacyInteractor):
    ''' Interactor that performs interaction using the agent login protocol.
    '''
    def __init__(self, auth_info):
        self._auth_info = auth_info

    def kind(self):
        '''Implement Interactor.kind by returning the agent kind'''
        return 'agent'

    def interact(self, client, location, interaction_required_err):
        '''Implement Interactor.interact by obtaining obtaining
        a macaroon from the discharger, discharging it with the
        local private key using the discharged macaroon as
        a discharge token'''
        p = interaction_required_err.interaction_method('agent',
                                                        InteractionInfo)
        if p.login_url is None or p.login_url == '':
            raise httpbakery.InteractionError(
                'no login-url field found in agent interaction method')
        agent = self._find_agent(location)
        if not location.endswith('/'):
            location += '/'
        login_url = urljoin(location, p.login_url)
        resp = requests.get(login_url, json={
            'Username': agent.username,
            'PublicKey': self._auth_info.key.encode().decode('utf-8'),
        })
        if resp.status_code != 200:
            raise httpbakery.InteractionError(
                'cannot acquire agent macaroon: {}'.format(resp.status_code)
            )
        m = resp.json().get('macaroon')
        if m is None:
            raise httpbakery.InteractionError('no macaroon in response')
        m = bakery.Macaroon.from_dict(m)
        ms = bakery.discharge_all(m, None, self._auth_info.key)
        b = bytearray()
        for m in ms:
            b.extend(utils.b64decode(m.serialize()))
        return httpbakery.DischargeToken(kind='agent', value=bytes(b))

    def _find_agent(self, location):
        ''' Finds an appropriate agent entry for the given location.
        :return Agent
        '''
        for a in self._auth_info.agents:
            # Don't worry about trailing slashes
            if a.url.rstrip('/') == location.rstrip('/'):
                return a
        raise httpbakery.InteractionMethodNotFound(
            'cannot find username for discharge location {}'.format(location))

    def legacy_interact(self, client, location, visit_url):
        '''Implement LegacyInteractor.legacy_interact by obtaining
        the discharge macaroon using the client's private key
        '''
        agent = self._find_agent(location)
        pk_encoded = self._auth_info.key.public_key.encode().decode('utf-8')
        value = {
            'username': agent.username,
            'public_key': pk_encoded,
        }
        # TODO(rogpeppe) use client passed into interact method.
        client = httpbakery.Client(key=self._auth_info.key)
        client.cookies.set_cookie(utils.cookie(
            url=visit_url,
            name='agent-login',
            value=base64.urlsafe_b64encode(
                json.dumps(value).encode('utf-8')).decode('utf-8'),
        ))
        resp = requests.get(url=visit_url, cookies=client.cookies, auth=client.auth())
        if resp.status_code != 200:
            raise httpbakery.InteractionError(
                'cannot acquire agent macaroon: {}'.format(resp.status_code))
        if not resp.json().get('agent-login', False):
            raise httpbakery.InteractionError('agent login failed')


class Agent(namedtuple('Agent', 'url, username')):
    ''' Represents an agent that can be used for agent authentication.
    @param url holds the URL of the discharger that knows about the agent (string).
    @param username holds the username agent (string).
    '''


class AuthInfo(namedtuple('AuthInfo', 'key, agents')):
    ''' Holds the agent information required to set up agent authentication
    information.

    It holds the agent's private key and information about the username
    associated with each known agent-authentication server.
    @param key the agent's private key (bakery.PrivateKey).
    @param agents information about the known agents (list of Agent).
    '''
