import json
import time
import requests
from mock import patch

from unittest2 import TestCase

from cosmic.api import API
from cosmic import cosmos
from dictionary import *

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
        res = self.d.get('/Language/0')
        self.assertEqual(json.loads(res.data), {
            "_links": {},
            "_data": "en"
        })

    def test_get_language_not_found(self):
        res = self.d.get('/Language/2')
        self.assertEqual(res.status_code, 404)

    def test_get_all_languages(self):
        res = self.d.get('/Language')
        self.assertEqual(json.loads(res.data), languages)

    def test_filter_languages(self):
        res = self.d.get('/Language?code="en"')
        self.assertEqual(json.loads(res.data), [languages[0]])

    def test_spec_endpoint(self):
        res = self.c.get('/spec.json')
        self.assertEqual(json.loads(res.data), json_spec)

