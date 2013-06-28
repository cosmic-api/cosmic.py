import json
import time
import requests
from mock import patch

from unittest2 import TestCase

from cosmic.api import API
from cosmic import cosmos
from dictionary import dictionary

json_spec = {
    u"name": u"dictionary",
    u"models": [
        {
            u"name": u"Language",
            u"schema": {u"type": u"String"},
            u"links": {
                u"map": {},
                u"order": []
            }
        },
        {
            u"name": u"Word",
            u"schema": {u"type": u"String"},
            u"links": {
                u"map": {
                    u"language": {
                        u"schema": {u"type": u"dictionary.Language"},
                        u"required": True
                    }
                },
                u"order": [u"language"]
            }
        }
    ],
    u"actions": {
        u"map": {},
        u"order": []
    }
}

class TestDictionary(TestCase):

    def setUp(self):
        self.c = dictionary.get_flask_app().test_client()
        self.d = dictionary.get_flask_app(debug=True).test_client()

    def test_get_language(self):
        res = self.d.get('/languages/0')
        self.assertEqual(json.loads(res.data), {
            "_links": {},
            "_data": "en"
        })

    def test_get_language_not_found(self):
        res = self.d.get('/languages/2')
        self.assertEqual(res.status_code, 404)

    def test_spec_endpoint(self):
        res = self.c.get('/spec.json')
        self.assertEqual(json.loads(res.data), json_spec)

