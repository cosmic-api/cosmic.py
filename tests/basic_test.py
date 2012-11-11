from flask.testsuite import FlaskTestCase
import json

from jsonschema import validate

import apio

api_schema = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "required": True
        },
        "url": {
            "type": "string",
            "required": True
        },
        "homepage": {
            "type": "string"
        },
        "models": {
            "type": "object",
            "patternProperties": {
                r'^[a-zA-Z0-9_]+$': {
                    "$ref": "http://json-schema.org/draft-03/schema#"
                }
            }
        },
        "actions": {
            "type": "object",
            "patternProperties": {
                r'^[a-zA-Z0-9_]+$': {
                    "type": "object",
                    "accepts": {
                        "$ref": "http://json-schema.org/draft-03/schema#"
                    },
                    "returns": {
                        "$ref": "http://json-schema.org/draft-03/schema#"
                    }
                }
            }
        }
    }
}

class TestApio(FlaskTestCase):

    def setup(self):

        self.testing_client = apio.MockClient()

        self.cookbook = apio.API('cookbook', "http://localhost:8881/api/", client=self.testing_client)

        @self.cookbook.action()
        def cabbage(params):
            if params['spicy']:
                return "Kimchi"
            else:
                return "Sauerkraut"

        self.cookbook.run()

        from flask import Flask
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.cookbook.get_blueprint(), url_prefix="/api")
        self.werkzeug_client = app.test_client()

        self.expected_schema = {
            'name': 'cookbook',
            'url': 'http://localhost:8881/api/',
            'actions': {
                'cabbage': {
                    'accepts': {
                        'type': 'any'
                    },
                    'returns': {
                        'type': 'any'
                    }
                }
            }
        }

    def test_serialize(self):
        self.assertEqual(self.cookbook.serialize(), self.expected_schema)

    def test_call(self):
        self.assertEqual(self.cookbook.call('cabbage', {'spicy': False}), "Sauerkraut")

    def test_spec_endpoint(self):
        res = self.werkzeug_client.get('/api/spec.json')
        self.assertEqual(json.loads(res.data), self.expected_schema)

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

    def test_action_okay(self):
        # Actions that declare parameters must be passed JSON data
        res = self.werkzeug_client.post('/api/actions/cabbage', data='{"spicy":true}', content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data), "Kimchi")

    def test_load(self):
        cookbook = apio.API.load('cookbook', client=self.testing_client)
        self.assertEqual(cookbook.call('cabbage', {'spicy': True}), "Kimchi")

    def test_schema(self):
        validate(self.cookbook.serialize(), api_schema)

if __name__ == '__main__':
    unittest.main()