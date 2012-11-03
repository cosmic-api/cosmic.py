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
        }
    }
}

def deep_equal(obj1, obj2):
    return json.dumps(obj1, sort_keys=True) == json.dumps(obj2, sort_keys=True)

class TestApio(unittest.TestCase):

    def setUp(self):
        self.cookbook = API('cookbook', "http://localhost:8881/api/")

    def test_serialize(self):
        self.assertEqual(self.cookbook.serialize(), {
            'name': 'cookbook',
            'url': 'http://localhost:8881/api/',
        })

    def test_schema(self):
        validate(self.cookbook.serialize(), api_schema)


if __name__ == '__main__':
    unittest.main()