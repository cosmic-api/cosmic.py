from unittest2 import TestCase

from flask import Flask

from apio.tools import *
from apio.http import *

class TestCORS(TestCase):
    """Test CORS support which is implemented in
    apio.tools.corsify_view
    """

    def setUp(self):
        app = Flask(__name__, static_folder=None)
        @corsify_view(["PUT"])
        def view():
            return "yes"
        app.add_url_rule('/box', 'box', view, methods=["PUT", "OPTIONS"])
        self.werkzeug_client = app.test_client()

    def test_CORS_preflight_request_okay(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "PUT"
        }
        res = self.werkzeug_client.open('/box', method="OPTIONS", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Access-Control-Allow-Methods"), "PUT")
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "http://example.com")

    def test_CORS_preflight_request_with_headers_okay(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "X-Wacky"
        }
        res = self.werkzeug_client.open('/box', method="OPTIONS", headers=headers)
        self.assertEqual(res.headers.get("Access-Control-Allow-Headers"), "X-Wacky")

    def test_CORS_preflight_request_no_origin(self):
        headers = {
            "Access-Control-Request-Method": "PUT"
        }
        res = self.werkzeug_client.open('/box', method="OPTIONS", headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Origin header")

    def test_CORS_preflight_request_disallowed_method(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST"
        }
        res = self.werkzeug_client.open('/box', method="OPTIONS", headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "must be set to PUT")

    def test_CORS_actual_request_okay(self):
        headers = {
            "Origin": "http://example.com",
            "X-Wacky": "Tobacky"
        }
        res = self.werkzeug_client.put('/box', headers=headers, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertRegexpMatches(res.data, "yes")

    def test_non_CORS_still_works(self):
        res = self.werkzeug_client.put('/box', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertRegexpMatches(res.data, "yes")

