from unittest2 import TestCase

from cosmic.tools import *
from cosmic.http import *


class TestCorsPreflightView(TestCase):

    def setUp(self):
        self.view = CorsPreflightView(["PUT"])

    def test_CORS_preflight_request_okay(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "PUT"
        }
        res = self.view(Request("OPTIONS", "", headers))
        self.assertEqual(res.code, 200)
        self.assertEqual(res.headers.get("Access-Control-Allow-Methods"), "PUT")
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "http://example.com")

    def test_CORS_preflight_request_with_headers_okay(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "X-Wacky"
        }
        res = self.view(Request("OPTIONS", "", headers))
        self.assertEqual(res.headers.get("Access-Control-Allow-Headers"), "X-Wacky")

    def test_CORS_preflight_request_no_origin(self):
        headers = {
            "Access-Control-Request-Method": "PUT"
        }
        res = self.view(Request("OPTIONS", "", headers))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "Origin header")

    def test_CORS_preflight_request_disallowed_method(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST"
        }
        res = self.view(Request("OPTIONS", "", headers))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "must be set to PUT")


class TestView(TestCase):

    def setUp(self):

        @make_view("POST")
        def noop(payload):
            pass
        self.noop = noop

        @make_view("POST")
        def unhandled_error(payload):
            return JSONData(1 / 0)
        self.unhandled_error = unhandled_error

        @make_view("POST")
        def api_error(payload):
            raise APIError("fizzbuzz")
        self.api_error = api_error

        @make_view("POST")
        def authentication_error(payload):
            raise AuthenticationError()
        self.authentication_error = authentication_error

        @make_view("POST")
        def validation_error(payload):
            raise ValidationError("Invalid!")
        self.validation_error = validation_error

    def test_wrong_content_type(self):
        res = self.noop(Request("POST", "", {"Content-Type": "application/jason"}))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "Content-Type must be")

    def test_invalid_json(self):
        res = self.noop(Request("POST", '{"spicy":farse}', {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "Invalid JSON")

    def test_unhandled_error(self):
        res = self.unhandled_error(Request("POST", "", {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 500)
        self.assertEqual(json.loads(res.body), {
            "error": "Internal Server Error"
        })

    def test_validation_error(self):
        res = self.validation_error(Request("POST", "", {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 400)
        self.assertEqual(json.loads(res.body), {
            "error": "Invalid!"
        })

    def test_unhandled_error_debug(self):
        @make_view("POST")
        def unhandled_error(payload):
            return 1 / 0
        with self.assertRaises(ZeroDivisionError):
            unhandled_error(Request("POST", "", {"Content-Type": "application/json"}), debug=True)

    def test_APIError_handling(self):
        res = self.api_error(Request("POST", "", {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 500)
        self.assertEqual(json.loads(res.body), {
            "error": "fizzbuzz"
        })

    def test_AuthenticationError_handling(self):
        res = self.authentication_error(Request("POST", "", {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 401)
        self.assertEqual(json.loads(res.body), {
            "error": "Authentication failed"
        })

    def test_action_no_args_no_data(self):
        res = self.noop(Request("POST", "", {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 200)
        self.assertEqual(res.body, "")

    def test_CORS_allow_origin(self):
        headers = {
            "Content-Type": "application/json",
            "Origin": "http://blabliblu.com"
        }
        res = self.noop(Request("POST", "", headers))
        self.assertEqual(res.headers["Access-Control-Allow-Origin"], headers["Origin"])
