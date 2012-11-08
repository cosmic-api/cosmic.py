import unittest
import json

from jsonschema import validate

from apio import API

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

        self.cookbook = cookbook = API('cookbook', "http://localhost:8881/api/")

        @cookbook.action()
        def cabbage(spicy=False):
            if spicy:
                return "Kimchi"
            else:
                return "Sauerkraut"

        from flask import Flask
        self.app = Flask(__name__, static_folder=None)
        self.app.register_blueprint(self.cookbook.get_blueprint(), url_prefix="/api")
        self.client = self.app.test_client()

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
        # http://werkzeug.pocoo.org/docs/routing/#werkzeug.routing.Map
        urls = self.app.url_map.bind('example.com')
        assert urls.test('/api/actions/cabbage')

    def test_spec_endpoint(self):
        res = self.client.get('/api/spec.json')
        assert json.loads(res.data) == self.expected_schema

    def test_schema(self):
        validate(self.cookbook.serialize(), api_schema)

if __name__ == '__main__':
    unittest.main()