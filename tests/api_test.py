import warnings
import json
import sys

from unittest2 import TestCase
from mock import patch

import requests
from teleport import *
from werkzeug.exceptions import Unauthorized

from cosmic.exceptions import *
from cosmic.api import API
from cosmic.models import Model, Cosmos
from cosmic import api, request

from cosmic import cosmos


cookbook_spec = {
    u'name': u'cookbook',
    u'actions': {
        u'map': {
            u'cabbage': {
                u'accepts': {
                    u'type': u"Struct",
                    u"param": {
                        u"map": {
                            u"spicy": {
                                u"required": True,
                                u"schema": {u"type": u"Boolean"}
                            },
                            u"capitalize": {
                                u"required": False,
                                u"schema": {u"type": u"Boolean"}
                            }
                        },
                        u"order": [u"spicy", u"capitalize"]
                    }
                },
                u'returns': {u'type': u'String'},
                u'doc': u"Yay cabbage"
            },
            u'noop': {
                u'doc': u"Does not do anything"
            }
        },
        u'order': [u'cabbage', u'noop']
    },
    u"models": {
        u"map": {
            u"Recipe": {
                u"data_schema": {
                    u'type': u"Struct",
                    u"param": {
                        u"map": {
                            u"name": {
                                u"required": True,
                                u"schema": {u"type": u"String"}
                            },
                        },
                        u"order": [u"name"]
                    }
                },
                u"links": {
                    u"map": {},
                    u"order": []
                },
                u"query_fields": {
                    u"map": {},
                    u"order": []
                }
            },
            u"Author": {
                u"data_schema": {
                    u'type': u"Struct",
                    u"param": {
                        u"map": {
                            u"is_gordon_ramsay": {
                                u"required": True,
                                u"schema": {u"type": u"Boolean"}
                            },
                        },
                        u"order": [u"is_gordon_ramsay"]
                    }
                },
                u"links": {
                    u"map": {},
                    u"order": []
                },
                u"query_fields": {
                    u"map": {},
                    u"order": []
                }
            }
        },
        u"order": [u"Recipe", u"Author"]
    }
}



class TestAPI(TestCase):

    def setUp(self):
        self.maxDiff = None
        self.cosmos = Cosmos()
        self.cosmos.__enter__()

        self.cookbook = cookbook = API(u'cookbook')

        @cookbook.action(
            accepts=Struct([
                required(u"spicy", Boolean),
                optional(u"capitalize", Boolean)
            ]),
            returns=String)
        def cabbage(spicy, capitalize=False):
            "Yay cabbage"
            if spicy:
                c = "kimchi"
            else:
                c = "sauerkraut"
            if capitalize:
                return c.capitalize()
            else:
                return c

        @cookbook.action(accepts=None, returns=None)
        def noop():
            "Does not do anything"
            pass

        @cookbook.model
        class Recipe(Model):
            properties = [
                required(u"name", String)
            ]

            @classmethod
            def validate(cls, datum):
                if datum["name"] == "bacon":
                    raise ValidationError("Not kosher")

        @cookbook.model
        class Author(Model):
            properties = [
                required(u"is_gordon_ramsay", Boolean)
            ]

        self.app_debug = self.cookbook.get_flask_app(debug=True)
        self.client_debug = self.app_debug.test_client()

        self.app = self.cookbook.get_flask_app()
        self.client = self.app.test_client()

    def tearDown(self):
        self.cosmos.__enter__()

    def test_model(self):
        R = self.cookbook.models.Recipe
        d = {
            "_links": {
                "self": {"href": "/Recipe/24"}
            },
            "name": "pancake"
        }
        with cosmos:
            self.assertEqual(Schema.to_json(R), {"type": "cookbook.Recipe"})
            pancake = R.from_json(d)
            self.assertEqual(pancake.name, "pancake")
            self.assertEqual(R.to_json(pancake), d)

    # TODO: Teleport should raise a ValidationError here
    def _test_accepts_invalid_schema(self):
        with self.assertRaisesRegexp(ValidationError, "Missing fields"):
            @self.cookbook.action(returns=Schema.from_json({"type": "Struct"}))
            def func(a, b=1):
                pass

    def test_model_deserialize_okay(self):
        with cosmos:
            s = Schema.from_json({"type": "cookbook.Recipe"})
            d = {
                "_links": {
                    "self": {"href": "/Recipe/14"}
                },
                "name": "turkey"
            }
            self.assertEqual(s.from_json(d).name, "turkey")

    def test_subclassing_hook(self):
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Author"]))

    def test_recursive_subclassing_hook(self):
        @self.cookbook.model
        class ChocolateAuthor(self.cookbook.models.Author):
            pass
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Author", "ChocolateAuthor"]))

    def test_model_schema_validation(self):
        with self.assertRaises(ValidationError):
            self.cookbook.models.Recipe.from_json(1.1)

    def test_model_custom_validation(self):
        with self.assertRaisesRegexp(ValidationError, "kosher"):
            self.cookbook.models.Recipe.from_json({
                "_links": {
                    "self": {"href": "/Recipe/123"}
                },
                "name": "bacon"
            })
        # When not overridden, custom validation passes
        self.cookbook.models.Author({'is_gordon_ramsay': True})

    def test_serialize(self):
        self.assertEqual(API.to_json(self.cookbook), cookbook_spec)

    def test_call_action_with_args(self):
        self.assertEqual(self.cookbook.actions.cabbage(spicy=False), "sauerkraut")

    def test_spec_endpoint(self):
        res = self.client.get('/spec.json')
        self.assertEqual(json.loads(res.data), cookbook_spec)

    def test_spec_wrong_method(self):
        res = self.client.get('/actions/noop')
        self.assertEqual(res.status_code, 405)
        res = self.client.post('/spec.json')
        self.assertEqual(res.status_code, 405)

    def test_wrong_content_type(self):
        res = self.client.post('/actions/cabbage', data="1", content_type="application/xml")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Content-Type")

    def test_action_okay(self):
        data = json.dumps({"spicy": True})
        res = self.client_debug.post('/actions/cabbage', data=data, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, '"kimchi"')

    def test_noop_action_okay(self):
        res = self.client_debug.post('/actions/noop', data='')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(res.data, '')

    def test_schema(self):
        with Cosmos():
            API.from_json(API.to_json(self.cookbook))

    def test_load_url(self):
        """Test the API.load function when given a spec URL"""
        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = cookbook_spec
            mock_get.return_value.status_code = 200
            with Cosmos():
                cookbook_decentralized = API.load('http://example.com/spec.json')
                self.assertEqual(API.to_json(cookbook_decentralized), cookbook_spec)



class TestRemoteAPI(TestCase):

    @classmethod
    def setUpClass(cls):
        from cosmic.http import RequestsPlugin
        cls.cosmos = Cosmos()
        cls.cosmos.__enter__()
        cls.cookbook = API.from_json(cookbook_spec)
        cls.cookbook.url = 'http://localhost:8881/api'
        cls.cookbook._request = RequestsPlugin('http://localhost:8881')

    @classmethod
    def tearDownClass(cls):
        cls.cosmos.__enter__()

    def test_remote_no_return_action(self):
        with patch.object(requests, 'request') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = ""
            self.assertEqual(self.cookbook.actions.noop(), None)
            mock_post.assert_called_with(
                url='http://localhost:8881/actions/noop',
                # Content-Type not added when data is empty
                headers={},
                method="POST",
                data="")

    def test_properties(self):
        self.assertEqual(self.cookbook.name, "cookbook")
        self.assertEqual(self.cookbook.url, "http://localhost:8881/api")

    def test_models(self):
        self.assertEqual(self.cookbook.models.__all__, ["Recipe", "Author"])

