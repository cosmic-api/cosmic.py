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

        @app.route('/noop', endpoint='noop', methods=["POST"])
        @apio_view(["POST"])
        def noop(payload):
            pass

        @app.route('/unhandled/error', endpoint='unhandled_error', methods=["POST"])
        @apio_view(["POST"])
        def noop(payload):
            return 1 / 0

        self.werkzeug_client = app.test_client()

    def test_wrong_content_type(self):
        res = self.werkzeug_client.post('/noop', content_type="application/jason")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Content-Type must be")

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

    def test_action_no_args_no_data(self):
        res = self.werkzeug_client.post('/noop', data='', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, "")
