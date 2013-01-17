from unittest2 import TestCase

from apio.tools import *
from apio.http import *

class TestCORSMiddleware(TestCase):
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


class TestStandardMiddleware(TestCase):
    """Tests our standard view wrappers as implemented in
    apio.http.standard_middleware
    """

    def setUp(self):

        def takes_string(payload):
            pass
        self.takes_string = standard_middleware(["POST"], {"type": "string"},
                                                None, False, takes_string)

        def noop(payload):
            pass
        self.noop = standard_middleware(["POST"], None, None, False, noop)

        def unhandled_error(payload):
            return 1 / 0
        self.unhandled_error = standard_middleware(["POST"], None, None, False,
                                                   unhandled_error)

        def api_error(payload):
            raise APIError("fizzbuzz")
        self.api_error = standard_middleware(["POST"], None, None, False,
                                             api_error)

        def authentication_error(payload):
            raise AuthenticationError()
        self.authentication_error = standard_middleware(["POST"], None, None,
                                                        False,
                                                        authentication_error)

    def test_wrong_content_type(self):
        res = self.noop(Request({"Content-Type": "application/jason"}, "", "POST"))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "Content-Type must be")

    def test_wrong_method(self):
        res = self.noop(Request({"Content-Type": "application/json"}, "", "PUT"))
        self.assertEqual(res.code, 405)
        self.assertRegexpMatches(res.body, "PUT is not allowed")

    def test_invalid_json(self):
        res = self.noop(Request({"Content-Type": "application/json"}, '{"spicy":farse}', "POST"))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "Invalid JSON")

    def test_validation_error(self):
        res = self.takes_string(Request({"Content-Type": "application/json"}, "true", "POST"))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "Validation failed")

    def test_no_data(self):
        res = self.takes_string(Request({"Content-Type": "application/json"}, "", "POST"))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "cannot be empty")

    def test_action_no_args_with_data(self):
        res = self.noop(Request({"Content-Type": "application/json"}, "true", "POST"))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(res.body, "must be empty")

    def test_unhandled_error(self):
        res = self.unhandled_error(Request({"Content-Type": "application/json"}, "", "POST"))
        self.assertEqual(res.code, 500)
        self.assertEqual(json.loads(res.body), {
            "error": "Internal Server Error"
        })

    def test_APIError_handling(self):
        res = self.api_error(Request({"Content-Type": "application/json"}, "", "POST"))
        self.assertEqual(res.code, 500)
        self.assertEqual(json.loads(res.body), {
            "error": "fizzbuzz"
        })

    def test_AuthenticationError_handling(self):
        res = self.authentication_error(Request({"Content-Type": "application/json"}, "", "POST"))
        self.assertEqual(res.code, 401)
        self.assertEqual(json.loads(res.body), {
            "error": "Authentication failed"
        })

    def test_action_no_args_no_data(self):
        res = self.noop(Request({"Content-Type": "application/json"}, "", "POST"))
        self.assertEqual(res.code, 200)
        self.assertEqual(res.body, "")

