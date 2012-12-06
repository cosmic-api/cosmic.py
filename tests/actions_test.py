import requests
import json

from unittest2 import TestCase
from mock import patch, Mock

from flask import Flask

from apio.api import ActionDispatcher
from apio.actions import Action, RemoteAction
from apio.exceptions import SpecError, APIError

class TestBasicRemoteAction(TestCase):

    def setUp(self):
        spec = {
            'name': 'cabbage',
            'accepts': {
                'type': 'object',
                'properties': {
                    'spicy': { 'type': 'any', 'required': True },
                    'capitalize': { 'type': 'any' }
                }
            },
            'returns': {
                'type': 'any'
            }
        }

        self.action = RemoteAction(spec, "http://example.com")

    def test_call_success(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = True
            self.action(spicy=True)
            mock_post.assert_called_with('http://example.com/actions/cabbage', headers={'Content-Type': 'application/json'}, data='{"spicy": true}')

    def test_call_no_args(self):
        with self.assertRaisesRegexp(SpecError, "takes arguments"):
            self.action()

    def test_call_failed_good_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json = { 'error': 'Too many servings' }
            with self.assertRaisesRegexp(APIError, "Too many servings"):
                self.action(spicy=True, servings=25)

    def test_call_failed_bad_response(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json = None
            with self.assertRaisesRegexp(APIError, "improper error response"):
                self.action(True)


class TestBasicAction(TestCase):

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

        def noop():
            return None

        self.noop = Action(noop)

        # Create test client for some HTTP tests
        app = Flask(__name__, static_folder=None)
        app.add_url_rule('/cabbage', 'cabbage', self.action.get_view(), methods=["POST"])
        app.add_url_rule('/noop', 'noop', self.noop.get_view(), methods=["POST"])
        self.werkzeug_client = app.test_client()

        # Test debug mode
        app_debug = Flask(__name__, static_folder=None)
        app_debug.config['PROPAGATE_EXCEPTIONS'] = True
        app_debug.add_url_rule('/cabbage', 'cabbage', self.action.get_view(debug=True), methods=["POST"])
        self.werkzeug_client_debug = app_debug.test_client()

    def test_successful_call(self):
        res = self.werkzeug_client.post('/cabbage', data='{"spicy":true}', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data), "12.0 pounds of kimchi")

    def test_successful_call_with_content_type_override(self):
        res = self.werkzeug_client.post('/cabbage?content_type_override=application%2Fjson', data='{"spicy":true}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data), "12.0 pounds of kimchi")

    def test_wrong_method(self):
        res = self.werkzeug_client.get('/cabbage', data='{"spicy":false}')
        self.assertEqual(res.status_code, 405)

    def test_wrong_content_type(self):
        res = self.werkzeug_client.post('/cabbage', data='{"spicy":false}', content_type="application/homer")
        self.assertEqual(res.status_code, 400)
        # Make sure Content-Type is mentioned in the error
        self.assertRegexpMatches(res.data, "Content-Type")

    def test_wrong_content_type_override(self):
        res = self.werkzeug_client.post('/cabbage?content_type_override=application%2Fhomer', data='{"spicy":false}')
        self.assertEqual(res.status_code, 400)
        # Make sure Content-Type is mentioned in the error
        self.assertRegexpMatches(res.data, "Content-Type")

    def test_invalid_json(self):
        res = self.werkzeug_client.post('/cabbage', data='{"spicy":farse}', content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Invalid JSON")

    def test_no_data(self):
        res = self.werkzeug_client.post('/cabbage', data='', content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "cannot be empty")

    def test_handled_exception(self):
        res = self.werkzeug_client_debug.post('/cabbage', data='{"spicy":true,"servings":25}', content_type="application/json")
        self.assertEqual(res.status_code, 501)
        self.assertEqual(json.loads(res.data), {
            "error": "Too many servings"
        })

    def test_unhandled_exception(self):
        res = self.werkzeug_client.post('/cabbage', data='{"spicy":true,"servings":0}', content_type="application/json")
        self.assertEqual(res.status_code, 500)
        self.assertEqual(json.loads(res.data), {
            "error": "Internal Server Error"
        })

    def test_unhandled_exception_debug(self):
        with self.assertRaises(ZeroDivisionError):
            self.werkzeug_client_debug.post('/cabbage', data='{"spicy":true,"servings":0}', content_type="application/json")

    def test_action_no_args_no_data(self):
        res = self.werkzeug_client.post('/noop', data='', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, "null")

    def test_action_no_args_with_data(self):
        res = self.werkzeug_client.post('/noop', data='true', content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "must be empty")

class TestActionAnnotation(TestCase):
    
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

    def test_args_accepts_compatible(self):
        def func(a, b=1):
            pass
        accepts = {
            "type": "object",
            "properties": {
                "a": {
                    "type": "boolean",
                    "required": True
                },
                "b": {
                    "type": "array",
                }
            }
        }
        action = Action(func, accepts=accepts)
        self.assertEqual(action.spec['accepts'], accepts)

    def _test_invalid_schema(self):
        def func(a, b=1):
            pass
        accepts = {
            "type": "bobject"
        }
        with self.assertRaisesRegexp(SpecError, "invalid"):
            action = Action(func, accepts=accepts)

class TestActionDispatcher(TestCase):
    
    def setUp(self):
        self.dispatcher = ActionDispatcher()
        length = Mock(return_value=3)
        length.spec = { 'name': 'length' }
        self.dispatcher.add(length)
        height = Mock()
        height.spec = { 'name': 'height' }
        self.dispatcher.add(height)

    def test_call(self):
        self.assertEqual(self.dispatcher.length([0, 1, 2]), 3)
    
    def test_iterate(self):
        l = [action for action in self.dispatcher]
        self.assertEqual(l[0].spec['name'], 'length')
        self.assertEqual(l[1].spec['name'], 'height')

    def test_specs(self):
        self.assertEqual(self.dispatcher.specs, [{ 'name': 'length' }, { 'name': 'height' }])

    def test_all(self):
        self.assertEqual(self.dispatcher.__all__, ['length', 'height'])

    def test_undefined_action(self):
        with self.assertRaisesRegexp(SpecError, "not defined"):
            self.dispatcher.width([0, 1, 2])


