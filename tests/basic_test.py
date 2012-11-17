from flask.testsuite import FlaskTestCase
from unittest2 import TestCase
import json
from mock import patch
import requests

from jsonschema import validate

import apio

index_spec = {
    'url': 'http://api.apio.io',
    'name': 'apio-index',
    'actions': {
        'register_api': {
            'returns': {'type': 'any'},
            'accepts': {'type': 'any'}
        },
        'get_spec': {
            'returns': {'type': 'any'},
            'accepts': {'type': 'any'}
        }
    }
}

cookbook_spec = {
    'name': 'cookbook',
    'url': 'http://localhost:8881/api',
    'actions': {
        'cabbage': {
            'accepts': {
                'type': 'any'
            },
            'returns': {
                'type': 'any'
            }
        },
        'noop': {
            'accepts': {
                'type': 'null'
            },
            'returns': {
                'type': 'any'
            }
        },
        'pounds_to_kilos': {
            'accepts': {
                'type': 'any'
            },
            'returns': {
                'type': 'any'
            }
        }
    }
}

class TestAPI(TestCase):

    def setUp(self):

        self.cookbook = apio.API('cookbook', "http://localhost:8881/api")

        @self.cookbook.action()
        def cabbage(params):
            if params['spicy']:
                return "kimchi"
            else:
                return "sauerkraut"

        @self.cookbook.action()
        def pounds_to_kilos(pounds):
            if pounds > 100:
                raise apio.APIError('Too many pounds', http_code=501)
            return 0.453592 * pounds * pounds / pounds

        @self.cookbook.action()
        def noop():
            pass

        with patch.object(requests, 'post') as mock_post:
            # Test initializing apio module
            mock_post.return_value.json = {
                "data": index_spec
            }
            apio.ensure_bootstrapped()
            # Register API
            mock_post.return_value.json = {
                "data": True
            }
            self.cookbook.run(register_api=True, dry_run=True)
            mock_post.assert_called_with('http://api.apio.io/actions/register_api', data=json.dumps(self.cookbook.spec))
            # Load API
            mock_post.return_value.json = {
                "data": cookbook_spec
            }
            self.remote_cookbook = apio.API.load('cookbook')
            mock_post.assert_called_with('http://api.apio.io/actions/get_spec', data=json.dumps("cookbook"))

        # Create test client for some HTTP tests
        from flask import Flask
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.cookbook.get_blueprint(), url_prefix="/api")
        self.werkzeug_client = app.test_client()

    def tearDown(self):
        apio.apis = {}

    def test_serialize(self):
        self.assertEqual(self.cookbook.spec, cookbook_spec)

    def test_call(self):
        self.assertEqual(self.cookbook.call('cabbage', {'spicy': False}), "sauerkraut")

    def test_spec_endpoint(self):
        res = self.werkzeug_client.get('/api/spec.json')
        self.assertEqual(json.loads(res.data), cookbook_spec)

    def test_action_wrong_method(self):
        # Actions can only be POST requests
        res = self.werkzeug_client.get('/api/actions/cabbage', data='{"spicy":false}')
        self.assertEqual(res.status_code, 405)

    def test_action_wrong_content_type(self):
        # Content type must be "application/json"
        res = self.werkzeug_client.post('/api/actions/cabbage', data='{"spicy":false}', content_type="application/homer")
        self.assertEqual(res.status_code, 400)

    def test_action_invalid_json(self):
        # Content type must be "application/json"
        res = self.werkzeug_client.post('/api/actions/cabbage', data='{"spicy":farse}', content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_action_no_data(self):
        # Actions that declare parameters must be passed JSON data
        res = self.werkzeug_client.post('/api/actions/cabbage')
        self.assertEqual(res.status_code, 400)

    def test_schema(self):
        validate(self.cookbook.spec, apio.API_SCHEMA)




    # First make sure provider returns the right HTTP response for the right HTTP request
    def test_local_successful_action(self):
        res = self.werkzeug_client.post('/api/actions/cabbage', data='{"spicy":true}', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data), {
            "data": "kimchi"
        })

    # ... Then make sure that this response is interpreted correctly on the consumer
    def test_remote_successful_action(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.json = {
                "data": 'kimchi'
            }
            self.assertEqual(self.remote_cookbook.call('cabbage', {'spicy': True}), "kimchi")
            mock_post.assert_called_with('http://localhost:8881/api/actions/cabbage', data=json.dumps({'spicy': True}))



    def test_local_no_return_action(self):
        res = self.werkzeug_client.post('/api/actions/noop', data='true', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data), {
            "data": None
        })

    def _test_remote_no_return_action(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.json = {
                "data": None
            }
            self.assertEqual(self.remote_cookbook.call('noop', True), None)
            mock_post.assert_called_with('http://localhost:8881/api/actions/noop', data=json.dumps(True))



    def test_local_raise_exception(self):
        res = self.werkzeug_client.post('/api/actions/pounds_to_kilos', data='101', content_type="application/json")
        self.assertEqual(res.status_code, 501)
        self.assertEqual(json.loads(res.data), {
            "error": "Too many pounds"
        })

    def test_remote_raise_exception(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.json = {
                "error": 'Too many pounds'
            }
            with self.assertRaises(apio.APIError):
                self.remote_cookbook.call('pounds_to_kilos', 101)




    def test_local_accidental_exception(self):
        res = self.werkzeug_client.post('/api/actions/pounds_to_kilos', data='0', content_type="application/json")
        self.assertEqual(res.status_code, 500)
        self.assertEqual(json.loads(res.data), {
            "error": "Internal Server Error"
        })

    def test_remote_raise_exception(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.json = {
                "error": 'Internal Server Error'
            }
            with self.assertRaises(apio.APIError) as cm:
                self.remote_cookbook.call('pounds_to_kilos', 101)
                self.assertEqual(cm.exception.message, "Internal Server Error")


    def test_load_url(self):
        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = cookbook_spec
            cookbook_decentralized = apio.API.load('http://example.com/spec.json')
            self.assertEqual(cookbook_decentralized.spec, cookbook_spec)


if __name__ == '__main__':
    unittest.main()