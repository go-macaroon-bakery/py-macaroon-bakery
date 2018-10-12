from unittest import TestCase

import macaroonbakery.httpbakery as httpbakery
import macaroonbakery.bakery as bakery


class TestWebBrowserInteractionInfo(TestCase):

    def test_from_dict(self):
        info_dict = {
            'VisitURL': 'https://example.com/visit',
            'WaitTokenURL': 'https://example.com/wait'}
        interaction_info = httpbakery.WebBrowserInteractionInfo.from_dict(info_dict)
        self.assertEqual(
            interaction_info.visit_url, 'https://example.com/visit')
        self.assertEqual(
            interaction_info.wait_token_url, 'https://example.com/wait')


class TestError(TestCase):

    def test_from_dict_upper_case_fields(self):
        err = httpbakery.Error.from_dict({
            'Message': 'm',
            'Code': 'c',
        })
        self.assertEqual(err, httpbakery.Error(
            code='c',
            message='m',
            info=None,
            version=bakery.LATEST_VERSION,
        ))

    def test_from_dict_lower_case_fields(self):
        err = httpbakery.Error.from_dict({
            'message': 'm',
            'code': 'c',
        })
        self.assertEqual(err, httpbakery.Error(
            code='c',
            message='m',
            info=None,
            version=bakery.LATEST_VERSION,
        ))
