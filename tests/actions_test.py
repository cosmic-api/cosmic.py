import requests
import json

from unittest2 import TestCase
from mock import patch, Mock

from cosmic.api import Namespace, API
from cosmic.actions import Action
from cosmic.exceptions import SpecError, APIError
from cosmic.http import Request
from cosmic.models import *
from cosmic.tools import normalize_schema, fetch_model

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
                        "schema": {'type': 'boolean'}
                    },
                    {
                        "name": 'capitalize',
                        "required": False,
                        "schema": {'type': 'boolean'}
                    }
                ]
            },
            'returns': {
                'type': 'string'
            }
        }

        self.action = Action.normalize(spec)

        # Without this, the action won't know its URL
        api = API.create("foodie")
        api.url = "http://example.com"
        self.action.api = api

    def test_call_success(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = "kimchi"
            self.action(spicy=True)
            mock_post.assert_called_with('http://example.com/actions/cabbage', headers={'Content-Type': 'application/json'}, data='{"spicy": true}')

    def test_call_no_args(self):
        with self.assertRaisesRegexp(ValidationError, "Expected data"):
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
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            self.action(spicy="yes")

    def test_call_invalid_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = 1
            with self.assertRaisesRegexp(APIError, "invalid value"):
                self.action(spicy=True, capitalize=True)


class TestBasicAction(TestCase):
    """Action is mostly glue code, the majority of interesting cases
    are tested in cosmic.http.cosmic_view
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

        self.action = Action.from_func(cabbage,
            accepts=normalize_schema({
                "type": "object",
                "properties": [
                    {
                        "name": "spicy",
                        "schema": {"type": "boolean"},
                        "required": True
                    },
                    {
                        "name": "servings",
                        "schema": {"type": "integer"},
                        "required": False
                    }
                ]
            }),
            returns=normalize_schema({"type": "string"}))
        self.view = self.action.get_view()

    def test_successful_call(self):
        res = self.view(Request("POST", '{"spicy":true}', {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 200)
        self.assertEqual(json.loads(res.body), "12.0 pounds of kimchi")

    def test_call_invalid_args(self):
        res = self.view(Request("POST", '{"spicy":1}', {"Content-Type": "application/json"}))
        self.assertEqual(res.code, 400)
        self.assertRegexpMatches(json.loads(res.body)["error"], "Invalid boolean")

    def test_unhandled_exception_debug(self):
        with self.assertRaises(ZeroDivisionError):
            self.view(Request("POST", '{"spicy":true,"servings":0}', {"Content-Type": "application/json"}), debug=True)


class TestActionWithModelData(TestCase):

    def setUp(self):

        def get_some(action):
            return action

        self.spec = {
            "name": "get_some",
            "accepts": {"type": "cosmic.Action"},
            "returns": {"type": "cosmic.Action"}
        }

        self.action = Action.from_func(get_some,
            accepts=normalize_schema({"type": "cosmic.Action"}),
            returns=normalize_schema({"type": "cosmic.Action"}))

        self.view = self.action.get_view()
        self.remote_action = Action.normalize(self.spec)

    def test_direct_call(self):
        self.assertEqual(self.action(self.action), self.action)

    def _test_remote_call(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = self.spec
            self.remote_action(self.action)

    def test_answer_request(self):
        res = self.view(Request("POST", json.dumps(self.spec), {"Content-Type": "application/json"}))
        answer = json.loads(res.body)
        self.assertEqual(self.spec, answer)


class TestActionAnnotation(TestCase):

    def setUp(self):
        self.a_schema = ObjectSchema({
            "properties": [
                {
                    "name": "a",
                    "required": True,
                    "schema": IntegerSchema()
                },
                {
                    "name": "b",
                    "required": False,
                    "schema": IntegerSchema()
                }
            ]
        })

    def test_no_args_accepts(self):
        def func():
            pass
        with self.assertRaisesRegexp(SpecError, "is said to take arguments"):
            action = Action.from_func(func, accepts={"type": "json"})

    def test_args_accepts_incompatible(self):
        def func(a, b=1):
            pass
        with self.assertRaisesRegexp(SpecError, "incompatible"):
            action = Action.from_func(func, accepts=BooleanSchema())

    def test_args_accepts_compatible_returns_compatible(self):
        def func(a, b=1):
            pass
        action = Action.from_func(func, accepts=self.a_schema, returns=self.a_schema)
        self.assertEqual(action.accepts, self.a_schema)
        self.assertEqual(action.returns, self.a_schema)


