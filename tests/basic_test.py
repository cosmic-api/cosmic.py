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

        self.apio_client = apio.MockClient()

        self.cookbook = apio.API('cookbook', "http://localhost:8881/api/", client=self.apio_client)

        @self.cookbook.action()
        def cabbage(params):
            if params['spicy']:
                return "Kimchi"
            else:
                return "Sauerkraut"

        self.cookbook.run()

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
        assert self.cookbook.serialize() == self.expected_schema

    def test_call(self):
        assert self.cookbook.call('cabbage', {'spicy': False}) == "Sauerkraut"

    def test_blueprint(self):
        from flask import Flask
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.cookbook.get_blueprint(), url_prefix="/api")
        werkzeug_client = app.test_client()
        # http://werkzeug.pocoo.org/docs/routing/#werkzeug.routing.Map
        urls = app.url_map.bind('example.com')
        assert urls.test('/api/actions/cabbage')
        res = werkzeug_client.get('/api/spec.json')
        assert json.loads(res.data) == self.expected_schema

    def test_load(self):
        cookbook = apio.API.load('cookbook', client=self.apio_client)
        assert cookbook.call('cabbage', {'spicy': True}) == "Kimchi"

    def test_schema(self):
        validate(self.cookbook.serialize(), api_schema)

if __name__ == '__main__':
    unittest.main()