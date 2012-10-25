import unittest
import json

from apio import API

def deep_equal(obj1, obj2):
    return json.dumps(obj1, sort_keys=True) == json.dumps(obj2, sort_keys=True)

class TestApio(unittest.TestCase):

    def setUp(self):
        pass

    def test_serialize(self):
        cookbook = API('cookbook', "http://localhost:8881/api/")
        self.assertEqual(cookbook.serialize(), {
            'name': 'cookbook',
            'url': 'http://localhost:8881/api/',
        })

if __name__ == '__main__':
    unittest.main()