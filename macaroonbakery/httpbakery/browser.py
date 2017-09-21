# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
import base64
from collections import namedtuple
import requests
from six.moves.urllib.parse import urljoin

from macaroonbakery.utils import visit_page_with_browser
from macaroonbakery.httpbakery.interactor import (
    Interactor, LegacyInteractor, WEB_BROWSER_INTERACTION_KIND,
    DischargeToken
)
from macaroonbakery.httpbakery.error import InteractionError


class WebBrowserInteractor(Interactor, LegacyInteractor):
    ''' Handles web-browser-based interaction-required errors by opening a
    web browser to allow the user to prove their credentials interactively.
    '''
    def __init__(self, open=None):
        if open is None:
            open = visit_page_with_browser
        self._open_web_browser = open

    def kind(self):
        return WEB_BROWSER_INTERACTION_KIND

    def legacy_interact(self, ctx, location, visit_url):
        self._open_web_browser(visit_url)

    def interact(self, ctx, location, ir_err):
        p = ir_err.interaction_method(self.kind(), WebBrowserInteractionInfo)
        if not location.endswith('/'):
            location += '/'
        visit_url = urljoin(location, p.visit_url)
        wait_token_url = urljoin(location, p.wait_token_url)
        self._open_web_browser(visit_url)
        return self.wait_for_token(ctx, wait_token_url)

    def wait_for_token(self, ctx, wait_token_url):
        ''' Returns a token from a the wait token URL
        :return DischargeToken
        '''
        resp = requests.get(wait_token_url)
        if resp.status_code != 200:
            raise InteractionError('cannot get {}'.format(wait_token_url))
        json_resp = resp.json()
        kind = json_resp.get('kind')
        if kind is None:
            raise InteractionError(
                'cannot get kind token from {}'.format(wait_token_url))
        token_val = json_resp.get('token')
        if token_val is None:
            token_val = json_resp.get('token64')
            if token_val is None:
                raise InteractionError(
                    'cannot get token from {}'.format(wait_token_url))
            token_val = base64.b64decode(token_val)
        return DischargeToken(kind=kind, value=token_val)


class WebBrowserInteractionInfo(namedtuple('WebBrowserInteractionInfo',
                                           'visit_url, wait_token_url')):
    ''' holds the information expected in the browser-window interaction
    entry in an interaction-required error.

    :param visit_url holds the URL to be visited in a web browser.
    :param wait_token_url holds a URL that will block on GET until the browser
    interaction has completed.
    '''
    @classmethod
    def deserialize(cls, info_dict):
        return WebBrowserInteractionInfo(visit_url=info_dict.get('VisitURL'),
                                         wait_token_url=info_dict('WaitURL'))
