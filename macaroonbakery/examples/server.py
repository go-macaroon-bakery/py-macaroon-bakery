# Copyright 2017 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.
from datetime import datetime, timedelta
import os

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer  # noqa
    from urlparse import urlparse  # noqa

import macaroonbakery
from macaroonbakery import checkers
from macaroonbakery import httpbakery


class GetHandler(BaseHTTPRequestHandler):
    def __init__(self, bakery, *args):
        self._bakery = bakery
        BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        auth_checker = self._bakery.checker.auth(
            httpbakery.extract_macaroons(self.headers)
        )
        ctx = checkers.AuthContext()
        try:
            auth_checker.allow(ctx, [macaroonbakery.Op(entity='get',
                                                       action='write')])
        except macaroonbakery.DischargeRequiredError as exc:
            m = self._bakery.oven.macaroon(
                httpbakery.request_version(self.headers),
                datetime.utcnow() + timedelta(minutes=5),
                exc.cavs(),
                exc.ops()
            )
            content, headers = httpbakery.discharged_required_response(
                m, '/', 'authz')
            self.send_response(401)
            for h in headers:
                self.send_header(h, headers[h])
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            return
        except macaroonbakery.PermissionDenied as exc:
            # Might be a Auth error
            self.send_response(401)
            self.end_headers()
            return
        self.send_response(200)
        message = 'authenticated\n'
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))


if __name__ == '__main__':

    key = macaroonbakery.generate_key()

    # move that to idm client module
    class IdmClient(macaroonbakery.IdentityClient):
        def declared_identity(self, ctx, declared):
            username = declared.get('username')
            if username is None:
                raise macaroonbakery.IdentityError('no user name found')
            return macaroonbakery.SimpleIdentity(user=username)

        def identity_from_context(self, ctx):
            return None, [
                checkers.Caveat(
                    location='https://api.jujucharms.com/identity',
                    condition='is-authenticated-user'
                )
            ]

    b = macaroonbakery.Bakery(
        location='test',
        locator=httpbakery.ThirdPartyLocator(),
        ops_store=None,
        key=key,
        identity_client=IdmClient(),
        checker=None,
        root_key_store=macaroonbakery.MemoryKeyStore(os.urandom(24)),
        authorizer=macaroonbakery.ACLAuthorizer(
            get_acl=lambda ctx, op: ['fabricematrat'],
            allow_public=False
        )
    )

    def handler(*args):
            GetHandler(b, *args)
    server = HTTPServer(('localhost', 8087), handler)
    print('Starting server at http://localhost:8087')
    server.serve_forever()
