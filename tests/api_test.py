import warnings
import json

from unittest2 import TestCase
from mock import patch

import requests

from apio.exceptions import *
from apio.tools import normalize
from apio.api import API, RemoteAPI, API_SCHEMA
from apio import api

index_spec = {
    'url': 'http://api.apio.io',
    'name': 'apio-index',
    'actions': [
        {
            'name': 'register_api',
            'returns': {'type': 'any'},
            'accepts': {'type': 'any'}
        },
        {
            'name': 'get_spec',
            'returns': {'type': 'any'},
            'accepts': {'type': 'any'}
        }
    ],
    "models": []
}

cookbook_spec = {
    'name': 'cookbook',
    'url': 'http://localhost:8881/api',
    'actions': [
        {
            'name': 'cabbage',
            'accepts': {
                'type': 'object',
                'properties': [
                    {
                        "name": "spicy",
                        "required": True,
                        "schema": {"type": "any"}
                    },
                    {
                        "name": "capitalize",
                        "required": False,
                        "schema": {"type": "any"}
                    }
                ]
            },
            'returns': {
                'type': 'any'
            }
        },
        {
            'name': 'noop',
            'returns': {
                'type': 'any'
            }
        }
    ],
    "models": [
        {
            "name": "Recipe",
            "schema": {"type": "string"}
        },
        {
            "name": "Cookie",
            "schema": {"type": "boolean"}
        }
    ]
}

class TestBootstrapping(TestCase):

    def test_successful(self):
        with patch.object(requests, 'post') as mock_post:
            # Test initializing apio module
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = index_spec
            api.ensure_bootstrapped()
            mock_post.assert_called_with('http://api.apio.io/actions/get_spec', headers={'Content-Type': 'application/json'}, data=json.dumps("apio-index"))
        self.assertTrue(isinstance(api.apio_index, RemoteAPI))

    def tearDown(self):
        api.clear_module_cache()


class TestAPI(TestCase):

    def setUp(self):

        self.cookbook = API('cookbook', "http://localhost:8881/api")

        @self.cookbook.action()
        def cabbage(spicy, capitalize=False):
            user = self.cookbook.authenticate()
            if spicy:
                c = "kimchi"
            else:
                c = "sauerkraut"
            if capitalize:
                return c.capitalize()
            else:
                return c

        @self.cookbook.action()
        def noop():
            return None

        @self.cookbook.authentication
        def authenticate(headers):
            if headers['X-Wacky'] != 'Tobacky':
                raise AuthenticationError()
            return "boronine"

        class Recipe(self.cookbook.Model):
            schema = {"type": "string"}
            def validate(self):
                if self.data == "bacon":
                    raise ValidationError("Not kosher")

        class Cookie(self.cookbook.Model):
            schema = {"type": "boolean"}

        api.apio_index = RemoteAPI(index_spec)

        with patch.object(requests, 'post') as mock_post:
            # Load API
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = cookbook_spec
            from apio.index import cookbook as remote_cookbook
            self.remote_cookbook = remote_cookbook
            mock_post.assert_called_with('http://api.apio.io/actions/get_spec', headers={'Content-Type': 'application/json'}, data=json.dumps("cookbook"))

        # Create test client for some HTTP tests
        from flask import Flask
        self.app = Flask(__name__, static_folder=None)
        self.app.register_blueprint(self.cookbook.get_blueprint(), url_prefix="/api")
        self.werkzeug_client = self.app.test_client()

    def tearDown(self):
        api.clear_module_cache()

    def test_subclassing_hook(self):
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Cookie"]))

    def test_recursive_subclassing_hook(self):
        class ChocolateCookie(self.cookbook.models.Cookie):
            pass
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Cookie", "ChocolateCookie"]))

    def test_model_illegal_schema(self):
        with self.assertRaises(ValidationError):
            class Pizza(self.cookbook.Model):
                schema = {"tipe": "object"}

    def test_model_schema_validation(self):
        with self.assertRaises(ValidationError):
            self.cookbook.models.Recipe(1.1)

    def test_model_custom_validation(self):
        with self.assertRaisesRegexp(ValidationError, "kosher"):
            self.cookbook.models.Recipe("bacon")
        # When not overridden, custom validation passes
        self.cookbook.models.Cookie(True)

    def test_register_api(self):
        with patch.object(requests, 'post') as mock_post:
            # Register API
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = True
            self.cookbook.run(register_api=True, dry_run=True)
            mock_post.assert_called_with('http://api.apio.io/actions/register_api', headers={'Content-Type': 'application/json'}, data=json.dumps(self.cookbook.spec))

    def test_serialize(self):
        self.assertEqual(self.cookbook.spec, cookbook_spec)

    def test_call(self):
        headers = { "X-Wacky": "Tobacky" }
        data = '{"spicy": true}'
        with self.app.test_request_context('/api/actions/cabbage', data=data, headers=headers, content_type="application/json"):
            self.assertEqual(self.cookbook.actions.cabbage(spicy=False), "sauerkraut")

    def test_spec_endpoint(self):
        res = self.werkzeug_client.get('/api/spec.json')
        self.assertEqual(json.loads(res.data), cookbook_spec)

    def test_schema(self):
        normalize(API_SCHEMA, self.cookbook.spec)

    def test_authentication_error(self):
        headers = { "X-Wacky": "Bananas" }
        data = '{"spicy": true}'
        res = self.werkzeug_client.post('/api/actions/cabbage', data=data, headers=headers, content_type="application/json")
        self.assertEqual(res.status_code, 401)

    def test_CORS_preflight_request_okay(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST"
        }
        res = self.werkzeug_client.open('/api/actions/cabbage', method="OPTIONS", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Access-Control-Allow-Methods"), "POST")
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "http://example.com")

    def test_CORS_preflight_request_with_headers_okay(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Wacky"
        }
        res = self.werkzeug_client.open('/api/actions/cabbage', method="OPTIONS", headers=headers)
        self.assertEqual(res.headers.get("Access-Control-Allow-Headers"), "X-Wacky")

    def test_CORS_preflight_request_no_origin(self):
        headers = {
            "Access-Control-Request-Method": "POST"
        }
        res = self.werkzeug_client.open('/api/actions/cabbage', method="OPTIONS", headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Origin header")

    def test_CORS_preflight_request_disallowed_method(self):
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "PUT"
        }
        res = self.werkzeug_client.open('/api/actions/cabbage', method="OPTIONS", headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "must be set to POST")

    def test_CORS_actual_request_okay(self):
        headers = {
            "Origin": "http://example.com",
            "X-Wacky": "Tobacky"
        }
        data = '{"spicy": true}'
        res = self.werkzeug_client.post('/api/actions/cabbage', data=data, headers=headers, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertRegexpMatches(res.data, "kimchi")

    def test_load_url(self):
        """Test the API.load function when given a spec URL"""
        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = cookbook_spec
            mock_get.return_value.status_code = 200
            cookbook_decentralized = API.load('http://example.com/spec.json')
            self.assertEqual(cookbook_decentralized.spec, cookbook_spec)

    def test_apierror_repr(self):
        """Make sure when APIError gets printed in stack trace we can see the message"""
        try:
            raise APIError("Blah")
        except APIError as e:
            self.assertEqual(unicode(e), "Blah")

class TestRemoteAPI(TestCase):

    def setUp(self):
        self.cookbook = RemoteAPI(cookbook_spec)

    def test_remote_no_return_action(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = None
            self.assertEqual(self.cookbook.actions.noop(), None)
            mock_post.assert_called_with('http://localhost:8881/api/actions/noop', headers={'Content-Type': 'application/json'}, data="")

    def test_properties(self):
        self.assertEqual(self.cookbook.name, "cookbook")
        self.assertEqual(self.cookbook.url, "http://localhost:8881/api")

    def test_model(self):
        self.assertEqual(self.cookbook.models.Recipe.schema, {"type": "string"})
        self.assertEqual(self.cookbook.models.Recipe.__bases__, (self.cookbook.Model,))

if __name__ == '__main__':
    unittest.main()
