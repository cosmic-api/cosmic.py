import json
import time
import copy
import requests

from mock import patch

from unittest2 import TestCase

from cosmic.api import API
from cosmic.http import WerkzeugTestClientPlugin
from cosmic import cosmos
from cosmic.testing import DBContext
from dictionary import *

json_spec = {
    u"name": u"dictionary",
    u"models": [
        {
            u"name": u"Language",
            u"data_schema": {
                u'type': u"Struct",
                u"param": {
                    u"map": {
                        u"code": {
                            u"required": True,
                            u"schema": {u"type": u"String"}
                        },
                    },
                    u"order": [u"code"]
                }
            },
            u"links": {
                u"map": {},
                u"order": []
            }
        },
        {
            u"name": u"Word",
            u"data_schema": {
                u'type': u"Struct",
                u"param": {
                    u"map": {
                        u"text": {
                            u"required": True,
                            u"schema": {u"type": u"String"}
                        },
                    },
                    u"order": [u"text"]
                }
            },
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
        self.maxDiff = 2000

    def test_local_links(self):
        with DBContext(langdb):
            hundo = Word.from_json(langdb["words"][1])
            self.assertEqual(hundo.language.code, "eo")
            self.assertEqual(hundo.id, "1")
            self.assertEqual(hundo.language.id, "1")

    def test_get_language(self):
        with DBContext(langdb):
            res = self.d.get('/Language/0')
            self.assertEqual(json.loads(res.data), langdb["languages"][0])

    def test_put_language(self):
        c = copy.deepcopy(langdb)
        english = copy.deepcopy(c["languages"][0])
        english["code"] = "english"
        with DBContext(c):
            res = self.d.put('/Language/0', data=json.dumps(english), content_type="application/json")
            self.assertEqual(c["languages"][0]["code"], "english")

    def test_get_language_not_found(self):
        with DBContext(langdb):
            res = self.d.get('/Language/2')
            self.assertEqual(res.status_code, 404)

    def test_get_all_languages(self):
        with DBContext(langdb):
            url = '/Language'
            res = self.d.get(url)
            self.assertEqual(json.loads(res.data), {
                "_links": {
                    "self": {"href": url}
                },
                "_embedded": {
                    "Language": langdb["languages"]
                }
            })

    def test_filter_languages(self):
        with DBContext(langdb):
            url = '/Language?code=%22en%22'
            res = self.d.get(url)
            self.assertEqual(json.loads(res.data), {
                "_links": {
                    "self": {"href": url}
                },
                "_embedded": {
                    "Language": [langdb["languages"][0]]
                }
            })

    def test_spec_endpoint(self):
        res = self.c.get('/spec.json')
        self.assertEqual(json.loads(res.data), json_spec)


class TestRemoteDictionary(TestCase):

    def setUp(self):
        client = dictionary.get_flask_app(debug=True).test_client()

        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = json_spec
            mock_get.return_value.status_code = 200

            with cosmos:
                self.dictionary = API.load('http://example.com/spec.json')
                self.dictionary._request = WerkzeugTestClientPlugin(client)

    def test_get_by_id(self):
        with DBContext(langdb):
            en = self.dictionary.models.Language.get_by_id("0")
            self.assertEqual(en.code, "en")


    def test_get_list(self):
        with DBContext(langdb):
            en = self.dictionary.models.Language.get_list(code="en")[0]
            self.assertEqual(en.code, "en")


