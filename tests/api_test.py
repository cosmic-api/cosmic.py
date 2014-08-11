import warnings
import json
import sys

from unittest2 import TestCase
from mock import patch

import requests
from cosmic.types import *
from werkzeug.exceptions import Unauthorized

from cosmic.exceptions import *
from cosmic.api import API
from cosmic.models import BaseModel, Cosmos
from cosmic import api, request


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
                u"properties": {
                    u"map": {
                        u"name": {
                            u"required": True,
                            u"schema": {u"type": u"String"}
                        },
                    },
                    u"order": [u"name"]
                },
                u"links": {
                    u"map": {},
                    u"order": []
                },
                u"query_fields": {
                    u"map": {},
                    u"order": []
                },
                u"list_metadata": {
                    u"map": {},
                    u"order": []
                },
                u'methods': {
                    u'get_by_id': False,
                    u'get_list': False,
                    u'create': False,
                    u'update': False,
                    u'delete': False,
                },
            },
            u"Author": {
                u"properties": {
                    u"map": {
                        u"is_gordon_ramsay": {
                            u"required": True,
                            u"schema": {u"type": u"Boolean"}
                        },
                    },
                    u"order": [u"is_gordon_ramsay"]
                },
                u"links": {
                    u"map": {},
                    u"order": []
                },
                u"query_fields": {
                    u"map": {},
                    u"order": []
                },
                u"list_metadata": {
                    u"map": {},
                    u"order": []
                },
                u'methods': {
                    u'get_by_id': False,
                    u'get_list': False,
                    u'create': False,
                    u'update': False,
                    u'delete': False,
                },
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
        class Recipe(BaseModel):
            properties = [
                required(u"name", String)
            ]

            @classmethod
            def validate_patch(cls, datum):
                if datum["name"] == "bacon":
                    raise ValidationError("Not kosher")

        @cookbook.model
        class Author(BaseModel):
            properties = [
                required(u"is_gordon_ramsay", Boolean)
            ]

        self.app_debug = self.cookbook.get_flask_app()
        self.app_debug.debug = True
        self.client_debug = self.app_debug.test_client()

        self.app = self.cookbook.get_flask_app()
        self.client = self.app.test_client()

    def tearDown(self):
        self.cosmos.__exit__(None, None, None)

    def test_model(self):
        R = self.cookbook.models.Recipe
        d = {
            "_links": {
                "self": {"href": "/Recipe/24"}
            },
            "name": "pancake"
        }

        (id, rep) = Representation(R).from_json(d)
        self.assertEqual(rep['name'], "pancake")
        self.assertEqual(Representation(R).to_json((id, rep)), d)

    def test_guess_methods(self):
        self.assertEqual(self.cookbook.models.Recipe.methods, [])

    def test_model_deserialize_okay(self):
        (id, rep) = Representation(self.cookbook.models.Recipe).from_json({
            "_links": {
                "self": {"href": "/Recipe/14"}
            },
            "name": "turkey"
        })
        self.assertEqual(rep['name'], "turkey")

    def test_subclassing_hook(self):
        self.assertEqual(set(self.cookbook.models.__dict__.keys()), set(["Recipe", "Author"]))

    def test_recursive_subclassing_hook(self):
        @self.cookbook.model
        class ChocolateAuthor(self.cookbook.models.Author):
            pass
        self.assertEqual(set(self.cookbook.models.__dict__.keys()), set(["Recipe", "Author", "ChocolateAuthor"]))

    def test_model_schema_validation(self):
        with self.assertRaises(ValidationError):
            Representation(self.cookbook.models.Recipe).from_json(1.1)

    def test_model_custom_validation(self):
        with self.assertRaisesRegexp(ValidationError, "kosher"):
            (id, rep) = Representation(self.cookbook.models.Recipe).from_json({
                "_links": {
                    "self": {"href": "/Recipe/123"}
                },
                "name": "bacon"
            })
            self.cookbook.models.Recipe.validate_patch(rep)
        # When not overridden, custom validation passes
        self.cookbook.models.Author(is_gordon_ramsay=True)

    def test_serialize(self):
        self.assertEqual(API.to_json(self.cookbook), cookbook_spec)

    def test_call_action_with_args(self):
        self.assertEqual(self.cookbook.actions.cabbage(spicy=False), "sauerkraut")

    def test_spec_endpoint(self):
        res = self.client_debug.get('/spec.json')
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
        API.from_json(API.to_json(self.cookbook))

