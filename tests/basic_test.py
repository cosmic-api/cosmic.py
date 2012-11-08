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

def deep_equal(obj1, obj2):
    return json.dumps(obj1, sort_keys=True) == json.dumps(obj2, sort_keys=True)

class TestApio(unittest.TestCase):

    def setUp(self):

        self.cookbook = cookbook = API('cookbook', "http://localhost:8881/api/")

        @cookbook.action()
        def cabbage(spicy=False):
            if spicy:
                return "Kimchi"
            else:
                return "Sauerkraut"

    def test_serialize(self):
        self.assertEqual(self.cookbook.serialize(), {
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
        })

    def test_blueprint(self):

        from flask import Flask
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.cookbook.get_blueprint(), url_prefix="/api")
        # http://werkzeug.pocoo.org/docs/routing/#werkzeug.routing.Map
        urls = app.url_map.bind('example.com')
        self.assertTrue(urls.test('/api/actions/cabbage'))

    def test_schema(self):
        validate(self.cookbook.serialize(), api_schema)

if __name__ == '__main__':
    unittest.main()