import requests
import json

from unittest2 import TestCase
from mock import patch, Mock

from apio.api import Namespace
from apio.actions import Action, RemoteAction
from apio.exceptions import SpecError, APIError
from apio.http import Request

class TestBasicRemoteAction(TestCase):

    def setUp(self):
        spec = {
            'name': 'cabbage',
            'accepts': {
                'type': 'object',
                'properties': [
                    {
                        "name": 'spicy',
                        "required": True,
                        "schema": { 'type': 'boolean' }
                    },
                    {
                        "name": 'capitalize',
                        "required": False,
                        "schema": { 'type': 'any' }
                    }
                ]
            },
            'returns': {
                'type': 'string'
            }
        }

        self.action = RemoteAction(spec, "http://example.com")

    def test_call_success(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = "kimchi"
            self.action(spicy=True)
            mock_post.assert_called_with('http://example.com/actions/cabbage', headers={'Content-Type': 'application/json'}, data='{"spicy": true}')

    def test_call_no_args(self):
        with self.assertRaisesRegexp(SpecError, "takes arguments"):
            self.action()

    def test_call_failed_good_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json = { 'error': 'Cannot capitalize' }
            with self.assertRaisesRegexp(APIError, "Cannot capitalize"):
                self.action(spicy=True, capitalize=True)

    def test_call_failed_bad_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json = None
            with self.assertRaisesRegexp(APIError, "improper error response"):
                self.action(spicy=True)

    def test_call_with_bad_args(self):
        with self.assertRaisesRegexp(SpecError, "Invalid boolean"):
            self.action(spicy="yes")

    def test_call_invalid_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = 1
            with self.assertRaisesRegexp(APIError, "invalid value"):
                self.action(spicy=True, capitalize=True)


class TestBasicAction(TestCase):
    """Action is mostly glue code, the majority of interesting cases
    are tested in apio.http.apio_view
    """

    def setUp(self):

        def cabbage(spicy, servings=1):
            if servings > 24:
                raise APIError("Too many servings", http_code=501)
            if spicy:
                c = "kimchi"
            else:
                c = "sauerkraut"
            return "%s pounds of %s" % (12.0 / servings, c)

        self.action = Action(cabbage)
        self.view = self.action.get_view()
        self.view_debug = self.action.get_view(debug=True)

    def test_successful_call(self):
        res = self.view.call(Request({"Content-Type": "application/json"}, '{"spicy":true}', "POST"))
        self.assertEqual(res.code, 200)
        self.assertEqual(json.loads(res.body), "12.0 pounds of kimchi")

    def test_unhandled_exception_debug(self):
        with self.assertRaises(ZeroDivisionError):
            self.view_debug.call(Request({"Content-Type": "application/json"}, '{"spicy":true,"servings":0}', "POST"))


class TestActionAnnotation(TestCase):

    def setUp(self):
        self.a_schema = {
            "type": "object",
            "properties": [
                {
                    "name": "a",
                    "required": True,
                    "schema": {"type": "boolean"}
                },
                {
                    "name": "b",
                    "required": False,
                    "schema": {"type": "integer"}
                }
            ]
        }
        self.a_bad_schema = {
            "type": "object",
            # Oops.. no properties
        }

    def test_no_args_no_accepts(self):
        def func():
            pass
        action = Action(func)
        self.assertTrue('accepts' not in action.spec.keys())

    def test_args_no_accepts(self):
        def func(a=None):
            pass
        action = Action(func)
        self.assertEqual(action.spec['accepts'], {"type": "any"})

    def test_no_args_accepts(self):
        def func():
            pass
        with self.assertRaisesRegexp(SpecError, "is said to take arguments"):
            action = Action(func, accepts={ "type": "any" })

    def test_args_accepts_incompatible(self):
        def func(a, b=1):
            pass
        with self.assertRaisesRegexp(SpecError, "incompatible"):
            action = Action(func, accepts={ "type": "boolean" })

    def test_args_accepts_compatible_returns_compatible(self):
        def func(a, b=1):
            pass
        action = Action(func, accepts=self.a_schema, returns=self.a_schema)
        self.assertEqual(action.spec['accepts'], self.a_schema)
        self.assertEqual(action.spec['returns'], self.a_schema)

    def test_accepts_invalid_schema(self):
        def func(a, b=1):
            pass
        with self.assertRaisesRegexp(SpecError, "invalid accepts"):
            action = Action(func, accepts=self.a_bad_schema)

    def test_accepts_invalid_schema(self):
        def func(a, b=1):
            pass
        with self.assertRaisesRegexp(SpecError, "invalid returns"):
            action = Action(func, returns=self.a_bad_schema)

    def test_invalid_schema(self):
        def func(a, b=1):
            pass
        accepts = {
            "type": "object"
            # Where are the properties?
        }
        with self.assertRaisesRegexp(SpecError, "invalid"):
            action = Action(func, accepts=accepts)
