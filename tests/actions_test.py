import requests

from unittest2 import TestCase
from mock import patch

from apio.actions import RemoteAction
from apio.exceptions import SpecError, APIError

class TestBasicRemoteAction(TestCase):

    def setUp(self):
        spec = {
            'name': 'simplify',
            'accepts': {
                'type': 'any'
            },
            'returns': {
                'type': 'any'
            }
        }
        self.action = RemoteAction(spec, "http://example.com")

    def test_call_success(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = True
            self.action(True)
            mock_post.assert_called_with('http://example.com/actions/simplify', headers={'Content-Type': 'application/json'}, data="true")
    
    def test_call_no_args(self):
        with self.assertRaisesRegexp(SpecError, "takes arguments"):
            self.action()

    def test_call_failed_good_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json = { 'error': '123' }
            with self.assertRaisesRegexp(APIError, "123"):
                self.action(True)

    def test_call_failed_bad_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json = None
            with self.assertRaisesRegexp(APIError, "improper error response"):
                self.action(True)
