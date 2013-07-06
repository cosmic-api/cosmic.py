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
        hundo = Word.from_json(words[1])
        self.assertEqual(hundo.language.data["code"], "eo")
        self.assertEqual(hundo.id, "1")
        self.assertEqual(hundo.language.id, "1")

    def test_get_language(self):
        res = self.d.get('/Language/0')
        self.assertEqual(json.loads(res.data), languages[0])

    def test_get_language_not_found(self):
        res = self.d.get('/Language/2')
        self.assertEqual(res.status_code, 404)

    def test_get_all_languages(self):
        url = '/Language'
        res = self.d.get(url)
        self.assertEqual(json.loads(res.data), {
            "_links": {
                "self": {"href": url}
            },
            "_embedded": {
                "Language": languages
            }
        })

    def test_filter_languages(self):
        url = '/Language?code=%22en%22'
        res = self.d.get(url)
        self.assertEqual(json.loads(res.data), {
            "_links": {
                "self": {"href": url}
            },
            "_embedded": {
                "Language": [languages[0]]
            }
        })

    def test_spec_endpoint(self):
        res = self.c.get('/spec.json')
        self.assertEqual(json.loads(res.data), json_spec)


class TestRemoteDictionary(TestCase):

    def setUp(self):
        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = json_spec
            mock_get.return_value.status_code = 200

            with cosmos:
                self.dictionary = API.load('http://example.com/spec.json')


    def test_get_by_id(self):

        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.content = json.dumps(languages[0])
            mock_get.return_value.status_code = 200

            en = self.dictionary.models.Language.get_by_id(0)
            self.assertEqual(en.data["code"], "en")

    def test_get_list(self):

        with patch.object(requests, 'get') as mock_get:
            url = '/Language?code=%22en%22'
            mock_get.return_value.content = json.dumps({
                "_links": {
                    "self": {"href": url}
                },
                "_embedded": {
                    "Language": [languages[0]]
                }
            })
            mock_get.return_value.status_code = 200

            en = self.dictionary.models.Language.get_list(code="en")[0]
            self.assertEqual(en.data["code"], "en")


