from unittest2 import TestCase

from flask import Flask

from apio.tools import *
from apio.http import *

class TestCORS(TestCase):
    """Test CORS support which is implemented in
    apio.http.cors_middleware
    """

    def setUp(self):
        def raw_view(req):
            return Response({}, "yes", 200)
        self.view = cors_middleware(["PUT"], raw_view)

    def test_CORS_preflight_request_okay(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "PUT"
        }
        res = self.view(Request(headers, "", "OPTIONS"))
        self.assertEqual(res.code, 200)
        self.assertEqual(res.headers.get("Access-Control-Allow-Methods"), "PUT")
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "http://example.com")

    def test_CORS_preflight_request_with_headers_okay(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "X-Wacky"
        }
        res = self.view(Request(headers, "", "OPTIONS"))
        self.assertEqual(res.headers.get("Access-Control-Allow-Headers"), "X-Wacky")

    def test_CORS_preflight_request_no_origin(self):
        headers = {
            "Access-Control-Request-Method": "PUT"
        }
        res = self.view(Request(headers, "", "OPTIONS"))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "Origin header")

    def test_CORS_preflight_request_disallowed_method(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST"
        }
        res = self.view(Request(headers, "", "OPTIONS"))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "must be set to PUT")

    def test_CORS_actual_request_okay(self):
        headers = {
            "Origin": "http://example.com",
            "X-Wacky": "Tobacky"
        }
        res = self.view(Request(headers, "", "PUT"))
        self.assertEqual(res.code, 200)
        self.assertRegexpMatches(res.body, "yes")

    def test_non_CORS_still_works(self):
        res = self.view(Request({}, "", "PUT"))
        self.assertEqual(res.code, 200)
        self.assertRegexpMatches(res.body, "yes")

class TestAPIOView(TestCase):
    """Tests our generic view wrapper implemented in
    apio.http.apio_view
    """

    def setUp(self):
        self.app = app = Flask(__name__, static_folder=None)

        @app.route('/takes/string', endpoint='takes_string', methods=["POST"])
        @apio_view(["POST"], accepts={"type": "string"})
        def takes_string(payload):
            pass

        @app.route('/noop', endpoint='noop', methods=ALL_METHODS)
        @apio_view(["POST"])
        def noop(payload):
            pass

        @app.route('/unhandled/error', endpoint='unhandled_error', methods=ALL_METHODS)
        @apio_view(["POST"])
        def noop(payload):
            return 1 / 0

        @app.route('/api/error', endpoint='api_error', methods=ALL_METHODS)
        @apio_view(["POST"])
        def noop(payload):
            raise APIError("fizzbuzz")

        @app.route('/authentication/error', endpoint='authentication_error', methods=ALL_METHODS)
        @apio_view(["POST"])
        def noop(payload):
            raise AuthenticationError()

        self.werkzeug_client = app.test_client()

    def test_wrong_content_type(self):
        res = self.werkzeug_client.post('/noop', content_type="application/jason")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Content-Type must be")

    def test_wrong_method(self):
        res = self.werkzeug_client.put('/noop', content_type="application/json")
        self.assertEqual(res.status_code, 405)
        self.assertRegexpMatches(res.data, "PUT is not allowed")

    def test_invalid_json(self):
        res = self.werkzeug_client.post('/noop', data='{"spicy":farse}', content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Invalid JSON")

    def test_validation_error(self):
        res = self.werkzeug_client.post('/takes/string', data="true", content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Validation failed")

    def test_no_data(self):
        res = self.werkzeug_client.post('/takes/string', data='', content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "cannot be empty")

    def test_action_no_args_with_data(self):
        res = self.werkzeug_client.post('/noop', data="true", content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "must be empty")

    def test_unhandled_exception(self):
        res = self.werkzeug_client.post('/unhandled/error', content_type="application/json")
        self.assertEqual(res.status_code, 500)
        self.assertEqual(json.loads(res.data), {
            "error": "Internal Server Error"
        })

    def test_APIError_handling(self):
        res = self.werkzeug_client.post('/api/error', content_type="application/json")
        self.assertEqual(res.status_code, 500)
        self.assertEqual(json.loads(res.data), {
            "error": "fizzbuzz"
        })

    def test_AuthenticationError_handling(self):
        res = self.werkzeug_client.post('/authentication/error', content_type="application/json")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(json.loads(res.data), {
            "error": "Authentication failed"
        })

    def test_action_no_args_no_data(self):
        res = self.werkzeug_client.post('/noop', data='', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, "")

