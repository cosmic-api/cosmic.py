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
from cosmic.models import Cosmos
from dictionary import *

json_spec = {
    u"name": u"dictionary",
    u"models": {
        u"map": {
            u"Language": {
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
                u"query_fields": {
                    u"map": {
                        u"code": {
                            u"required": False,
                            u"schema": {u"type": u"String"}
                        }
                    },
                    u"order": [u"code"]
                },
                u"links": {
                    u"map": {},
                    u"order": []
                }
            },
            u"Word": {
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
                },
                u"query_fields": {
                    u"map": {},
                    u"order": []
                },
            }
        },
        u"order": [u"Language", u"Word"]
    },
    u"actions": {
        u"map": {},
        u"order": []
    }
}

class TestDictionary(TestCase):

    def setUp(self):
        self.c = dictionary.get_flask_app().test_client()
        self.d = dictionary.get_flask_app(debug=True).test_client()

        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = json_spec
            mock_get.return_value.status_code = 200

            with Cosmos():
                self.remote_dictionary = API.load('http://example.com/spec.json')
                # Use the local API's HTTP client to simulate the remote API's calls
                self.remote_dictionary._request = WerkzeugTestClientPlugin(self.d)

        self.maxDiff = 2000


    def _test_create_model(self, word_model):
        c = copy.deepcopy(langdb)
        with DBContext(c) as dbctx:
            birdo = word_model({
                "text": "birdo",
                "_links": {
                    "language": {"href": "/Language/1"}
                }
            })
            self.assertEqual(birdo.id, None)
            birdo.save()
            self.assertEqual(birdo.id, "2")

    def test_local_create_model(self):
        self._test_create_model(Word)

    def test_remote_create_model(self):
        self._test_create_model(self.remote_dictionary.models.Word)


    def _test_delete(self, word_model):
        c = copy.deepcopy(langdb)
        with DBContext(c) as dbctx:
            hundo = word_model.get_by_id("1")
            hundo.delete()
            self.assertEqual(c["words"][1], None)

    def test_local_delete(self):
        self._test_delete(Word)

    def test_remote_delete(self):
        self._test_delete(self.remote_dictionary.models.Word)


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

    def test_delete_language(self):
        c = copy.deepcopy(langdb)
        with DBContext(c):
            res = self.d.delete('/Language/0', content_type="application/json")
            self.assertEqual(c["languages"][0], None)

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
        res = self.d.get('/spec.json')
        self.assertEqual(json.loads(res.data), json_spec)



