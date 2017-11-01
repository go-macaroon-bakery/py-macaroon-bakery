# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from macaroonbakery.httpbakery.client import (
    BakeryException,
    Client,
    extract_macaroons,
)
from macaroonbakery.httpbakery.error import (
    BAKERY_PROTOCOL_HEADER,
    DischargeError,
    ERR_DISCHARGE_REQUIRED,
    ERR_INTERACTION_REQUIRED,
    Error,
    ErrorInfo,
    InteractionError,
    InteractionMethodNotFound,
    discharge_required_response,
    request_version,
)
from macaroonbakery.httpbakery.keyring import ThirdPartyLocator
from macaroonbakery.httpbakery.interactor import (
    DischargeToken,
    Interactor,
    LegacyInteractor,
    WEB_BROWSER_INTERACTION_KIND,
)
from macaroonbakery.httpbakery.browser import (
    WebBrowserInteractionInfo,
    WebBrowserInteractor,
)
from macaroonbakery.httpbakery.discharge import discharge

__all__ = [
    'BAKERY_PROTOCOL_HEADER',
    'BakeryException',
    'Client',
    'DischargeError',
    'DischargeToken',
    'ERR_DISCHARGE_REQUIRED',
    'ERR_INTERACTION_REQUIRED',
    'Error',
    'ErrorInfo',
    'InteractionError',
    'InteractionMethodNotFound',
    'Interactor',
    'LegacyInteractor',
    'ThirdPartyLocator',
    'WEB_BROWSER_INTERACTION_KIND',
    'WebBrowserInteractionInfo',
    'WebBrowserInteractor',
    'discharge',
    'discharge_required_response',
    'extract_macaroons',
    'request_version',
]
