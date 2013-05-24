from unittest2 import TestCase

from werkzeug.exceptions import Unauthorized, BadRequest
from flask import Flask

from cosmic.tools import *
from cosmic.http import *

from teleport import ValidationError, Box


class TestView(TestCase):

    def setUp(self):

        def noop(payload):
            pass
        self.noop = FlaskView(noop, False)

        def unhandled_error(payload):
            return Box(1 / 0)
        self.unhandled_error = FlaskView(unhandled_error, False)

        def authentication_error(payload):
            raise Unauthorized()
        self.authentication_error = FlaskView(authentication_error, False)

        def bad_request(payload):
            raise BadRequest("BOOM")
        self.bad_request = FlaskView(bad_request, False)

        def validation_error(payload):
            raise ValidationError("Invalid!")
        self.validation_error = FlaskView(validation_error, False)

        self.app = Flask(__name__)
        self.app.debug = True

    def test_wrong_content_type(self):
        with self.app.test_request_context('/', method="POST", data="", content_type="application/jason"):
            res = self.noop()
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.content_type, "application/json")
            self.assertRegexpMatches(res.data, "Content-Type must be")

    def test_invalid_json(self):
        with self.app.test_request_context('/', method="POST", data='{"spicy":farse}', content_type="application/json"):
            res = self.noop()
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.content_type, "application/json")
            self.assertRegexpMatches(res.data, "Invalid JSON")

    def test_unhandled_error(self):
        with self.app.test_request_context('/', method="POST", data="", content_type="application/json"):
            res = self.unhandled_error()
            self.assertEqual(res.status_code, 500)
            self.assertEqual(res.content_type, "application/json")
            self.assertEqual(json.loads(res.data), {
                "error": "Internal Server Error"
            })

    def test_validation_error(self):
        with self.app.test_request_context('/', method="POST", data="", content_type="application/json"):
            res = self.validation_error()
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.content_type, "application/json")
            self.assertEqual(json.loads(res.data), {"error": "Invalid!"})

    def test_unhandled_error_debug(self):
        u = FlaskView(
            view=self.unhandled_error.view,
            debug=True)
        with self.assertRaises(ZeroDivisionError):
            with self.app.test_request_context('/', method="POST", data="", content_type="application/json"):
                u()

    def test_HTTPException_handling(self):
        with self.app.test_request_context('/', method="POST", data="", content_type="application/json"):
            res = self.authentication_error()
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.content_type, "application/json")
            self.assertEqual(json.loads(res.data), {"error": "Unauthorized"})

    def test_HTTPException_with_description_handling(self):
        with self.app.test_request_context('/', method="POST", data="", content_type="application/json"):
            res = self.bad_request()
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.content_type, "application/json")
            self.assertEqual(json.loads(res.data), {"error": "BOOM"})

    def test_action_no_args_no_data(self):
        with self.app.test_request_context('/', method="POST", data="", content_type="application/json"):
            res = self.noop()
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.content_type, "application/json")
            self.assertEqual(res.data, "")

