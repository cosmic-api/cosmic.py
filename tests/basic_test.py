import unittest
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

class TestApio(unittest.TestCase):

    def setUp(self):

        self.apio_client = apio.MockClient()

        self.cookbook = apio.API('cookbook', "http://localhost:8881/api/", client=self.apio_client)

        @self.cookbook.action()
        def cabbage(spicy=False):
            if spicy:
                return json.dumps("Kimchi")
            else:
                return json.dumps("Sauerkraut")

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
        assert cookbook.call('cabbage', None) == "Sauerkraut"

    def test_schema(self):
        validate(self.cookbook.serialize(), api_schema)

if __name__ == '__main__':
    unittest.main()