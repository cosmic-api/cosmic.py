import warnings
import json

from unittest2 import TestCase
from mock import patch

import requests
import jsonschema

from apio.exceptions import *
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
    ]
}

cookbook_spec = {
    'name': 'cookbook',
    'url': 'http://localhost:8881/api',
    'actions': [
        {
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
        },
        {
            'name': 'noop',
            'returns': {
                'type': 'any'
            }
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

        @self.cookbook.action
        def cabbage(spicy, capitalize=False):
            if spicy:
                c = "kimchi"
            else:
                c = "sauerkraut"
            if capitalize:
                return c.capitalize()
            else:
                return c

        @self.cookbook.action
        def noop():
            return None

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
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.cookbook.get_blueprint(), url_prefix="/api")
        self.werkzeug_client = app.test_client()

    def tearDown(self):
        api.clear_module_cache()

    def test_register_api(self):
        with patch.object(requests, 'post') as mock_post:
            # Register API
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = True
            self.cookbook.run(register_api=True, dry_run=True)
            mock_post.assert_called_with('http://api.apio.io/actions/register_api', headers={'Content-Type': 'application/json'}, data=json.dumps(self.cookbook.spec))

    def test_import_actions(self):
        from apio.index.cookbook import actions
        self.assertEqual(actions, self.remote_cookbook.actions)
    
    def test_import_specific_action(self):
        from apio.index.cookbook.actions import cabbage
        self.assertEqual(cabbage, self.remote_cookbook.actions.cabbage)

    def test_import_all_actions(self):
        with warnings.catch_warnings():
            # Warning about importing * at non-module level. Thanks mom..
            warnings.simplefilter("ignore")
            from apio.index.cookbook.actions import *
            self.assertEqual(cabbage, self.remote_cookbook.actions.cabbage)
            self.assertEqual(noop, self.remote_cookbook.actions.noop)
        
    def test_serialize(self):
        self.assertEqual(self.cookbook.spec, cookbook_spec)

    def test_call(self):
        self.assertEqual(self.cookbook.actions.cabbage(spicy=False), "sauerkraut")

    def test_spec_endpoint(self):
        res = self.werkzeug_client.get('/api/spec.json')
        self.assertEqual(json.loads(res.data), cookbook_spec)

    def test_action_no_args_no_data(self):
        res = self.werkzeug_client.post('/api/actions/noop', data='', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, "null")

    def test_schema(self):
        store = {
            "http://json-schema.org/draft-03/schema": jsonschema.Draft3Validator.META_SCHEMA
        }
        jsonschema.validate(self.cookbook.spec, API_SCHEMA, schema_store=store)

    def test_local_no_return_action(self):
        res = self.werkzeug_client.post('/api/actions/noop', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data), None)

    def test_remote_no_return_action(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = None
            self.assertEqual(self.remote_cookbook.actions.noop(), None)
            mock_post.assert_called_with('http://localhost:8881/api/actions/noop', headers={'Content-Type': 'application/json'}, data="")

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


if __name__ == '__main__':
    unittest.main()
