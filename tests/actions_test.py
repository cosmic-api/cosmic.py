import requests
import json

from unittest2 import TestCase
from mock import patch, Mock

from teleport import *
from werkzeug.exceptions import InternalServerError

from cosmic.api import Namespace, API
from cosmic.actions import Action, ActionSerializer
from cosmic.exceptions import SpecError

from cosmic import cosmos


class TestBasicRemoteAction(TestCase):

    def setUp(self):
        spec = {
            'name': 'cabbage',
            'accepts': {
                'type': "struct",
                "fields": [
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

        self.action = ActionSerializer().deserialize(spec)

        # Without this, the action won't know its URL
        api = API("foodie")
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
            with self.assertRaisesRegexp(InternalServerError, "Cannot capitalize"):
                self.action(spicy=True, capitalize=True)

    def test_call_failed_bad_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json = None
            with self.assertRaisesRegexp(InternalServerError, "improper error response"):
                self.action(spicy=True)

    def test_call_with_bad_args(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            self.action(spicy="yes")

    def test_call_invalid_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = 1
            with self.assertRaisesRegexp(InternalServerError, "invalid value"):
                self.action(spicy=True, capitalize=True)


class TestActionWithModelData(TestCase):

    def setUp(self):

        def get_some(action):
            return action

        self.spec = {
            "name": "get_some",
            "accepts": {"type": "cosmic.Action"},
            "returns": {"type": "cosmic.Action"}
        }

        with cosmos:
            self.action = Action.from_func(get_some,
                accepts=Schema().deserialize({"type": "cosmic.Action"}),
                returns=Schema().deserialize({"type": "cosmic.Action"}))

            self.remote_action = ActionSerializer().deserialize(self.spec)

    def test_direct_call(self):
        self.assertEqual(self.action(self.action), self.action)

    def _test_remote_call(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = self.spec
            self.remote_action(self.action)

    def test_answer_request(self):
        with cosmos:
            answer = self.action.json_to_json(Box(self.spec))
            self.assertEqual(self.spec, answer.datum)


class TestActionAnnotation(TestCase):

    def setUp(self):
        self.a_schema = Struct([
            required("a", Integer()),
            optional("b", Integer())
        ])

    def test_no_args_accepts(self):
        def func():
            pass
        with self.assertRaisesRegexp(SpecError, "is said to take arguments"):
            action = Action.from_func(func, accepts={"type": "json"})

    def test_args_accepts_incompatible(self):
        def func(a, b=1):
            pass
        with self.assertRaisesRegexp(SpecError, "incompatible"):
            action = Action.from_func(func, accepts=Boolean())

    def test_args_accepts_compatible_returns_compatible(self):
        def func(a, b=1):
            pass
        action = Action.from_func(func, accepts=self.a_schema, returns=self.a_schema)
        self.assertEqual(action.accepts, self.a_schema)
        self.assertEqual(action.returns, self.a_schema)

