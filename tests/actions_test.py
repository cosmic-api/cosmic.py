import requests
import json

from unittest2 import TestCase
from mock import patch, Mock

from apio.api import Namespace
from apio.actions import Action, RemoteAction
from apio.exceptions import SpecError, APIError
from apio.http import Request
from apio.models import *

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

        self.action = RemoteAction.normalize(spec)
        self.action.api_url = "http://example.com"

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
            mock_post.return_value.json = {'error': 'Cannot capitalize'}
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

        self.action = Action(cabbage, returns=JSONSchema())
        self.view = self.action.get_view()

    def test_successful_call(self):
        res = self.view(Request("POST", '{"spicy":true}', {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 200)
        self.assertEqual(json.loads(res.body), "12.0 pounds of kimchi")

    def test_unhandled_exception_debug(self):
        with self.assertRaises(ZeroDivisionError):
            self.view(Request("POST", '{"spicy":true,"servings":0}', {"Content-Type": "application/json"}), debug=True)

class TestActionAnnotation(TestCase):

    def setUp(self):
        self.a_schema = ObjectSchema([
            {
                "name": "a",
                "required": True,
                "schema": BooleanSchema()
            },
            {
                "name": "b",
                "required": False,
                "schema": IntegerSchema()
            }
        ])

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
            action = Action(func, accepts=BooleanSchema())

    def test_args_accepts_compatible_returns_compatible(self):
        def func(a, b=1):
            pass
        action = Action(func, accepts=self.a_schema, returns=self.a_schema)
        self.assertEqual(action.accepts, self.a_schema)
        self.assertEqual(action.returns, self.a_schema)


