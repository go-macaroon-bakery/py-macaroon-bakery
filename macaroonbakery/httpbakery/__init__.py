# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from macaroonbakery.httpbakery.client import (
    BakeryAuth, extract_macaroons, BakeryException, acquire_discharge
)
from macaroonbakery.httpbakery.error import (
    BAKERY_PROTOCOL_HEADER, discharge_required_response, request_version,
    ERR_INTERACTION_REQUIRED, ERR_DISCHARGE_REQUIRED,
    InteractionMethodNotFound, InteractionError, DischargeError,
    InteractionRequiredError, Error, ErrorInfo
)
from macaroonbakery.httpbakery.keyring import ThirdPartyLocator
from macaroonbakery.httpbakery.interactor import (
    DischargeToken, LegacyInteractor, WEB_BROWSER_INTERACTION_KIND
)

from macaroonbakery.httpbakery.discharge import discharge
from macaroonbakery.httpbakery.agent import (
    load_agent_file, Agent, AgentInteractor, AgentFileFormatError, AuthInfo
)
from macaroonbakery.httpbakery.browser import (
    WebBrowserInteractor, WebBrowserInteractionInfo
)

__all__ = [
    'Agent',
    'AgentInteractor',
    'AgentFileFormatError',
    'AuthInfo',
    'BAKERY_PROTOCOL_HEADER',
    'BakeryAuth',
    'BakeryException',
    'DischargeError',
    'DischargeToken',
    'ERR_DISCHARGE_REQUIRED',
    'ERR_INTERACTION_REQUIRED',
    'Error',
    'ErrorInfo',
    'InteractionError',
    'InteractionMethodNotFound',
    'InteractionRequiredError',
    'LegacyInteractor',
    'ThirdPartyLocator',
    'WEB_BROWSER_INTERACTION_KIND',
    'WebBrowserInteractionInfo',
    'WebBrowserInteractor',
    'acquire_discharge',
    'discharge',
    'discharge_required_response',
    'extract_macaroons',
    'load_agent_file',
    'request_version',
]
