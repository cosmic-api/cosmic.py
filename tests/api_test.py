import warnings
import json
import sys

from unittest2 import TestCase
from mock import patch

import requests
from teleport import *
from werkzeug.exceptions import Unauthorized

from cosmic.exceptions import *
from cosmic.api import API, APISerializer
from cosmic.models import Model, S, LazyS
from cosmic import api, request

from cosmic import cosmos


cookbook_spec = {
    u'name': u'cookbook',
    u'actions': [
        {
            u'name': u'cabbage',
            u'accepts': {
                u'type': u"struct",
                u"fields": [
                    {
                        u"name": u"spicy",
                        u"required": True,
                        u"schema": {u"type": u"boolean"}
                    },
                    {
                        u"name": u"capitalize",
                        u"required": False,
                        u"schema": {u"type": u"boolean"}
                    }
                ]
            },
            u'returns': {
                u'type': u'json'
            }
        },
        {
            u'name': u'noop'
        }
    ],
    u"models": [
        {
            u"name": u"Recipe",
            u"schema": {u"type": u"string"}
        },
        {
            u"name": u"Cookie",
            u"schema": {u"type": u"boolean"}
        }
    ]
}



class TestAPI(TestCase):

    def setUp(self):
        self.maxDiff = None

        self.cookbook = API(u'cookbook')

        @self.cookbook.action(
            accepts=Schema().deserialize({
                "type": u"struct",
                "fields": [
                    {
                        "name": u"spicy",
                        "schema": {"type": u"boolean"},
                        "required": True
                    },
                    {
                        "name": u"capitalize",
                        "schema": {"type": u"boolean"},
                        "required": False
                    }
                ]
            }),
            returns=JSON())
        def cabbage(spicy, capitalize=False):
            if spicy:
                c = "kimchi"
            else:
                c = "sauerkraut"
            if capitalize:
                return c.capitalize()
            else:
                return c

        @self.cookbook.action(accepts=None, returns=None)
        def noop():
            pass

        @self.cookbook.model
        class Recipe(Model):
            schema = String()

            @classmethod
            def instantiate(cls, datum):
                if datum == "bacon":
                    raise ValidationError("Not kosher")
                return cls(datum)

        @self.cookbook.model
        class Cookie(Model):
            schema = Boolean()


        self.app = self.cookbook.get_flask_app(debug=True)
        self.werkzeug_client = self.app.test_client()

    def test_S(self):
        R = self.cookbook.models.Recipe
        self.assertEqual(S(R).serialize_self(), {"type": "cookbook.Recipe"})
        pancake = S(R).deserialize("pancake")
        self.assertEqual(pancake.data, u"pancake")
        self.assertEqual(S(R).serialize(pancake), u"pancake")

    def test_LazyS_okay(self):
        class LS(LazyS):
            _name = "cookbook.Recipe"
        ls = LS()
        self.assertEqual(ls.serialize_self(), {"type": "cookbook.Recipe"})
        # This time model_cls should be cached
        self.assertEqual(ls.serialize_self(), {"type": "cookbook.Recipe"})

    def test_LazyS_fail(self):
        class LS(LazyS):
            _name = "unknown.Unknown"
        ls = LS()
        with self.assertRaises(ModelNotFound):
            ls.deserialize(1)

    def test_accepts_invalid_schema(self):
        with self.assertRaisesRegexp(ValidationError, "Missing fields"):
            @self.cookbook.action(returns=Schema().deserialize({"type": "struct"}))
            def func(a, b=1):
                pass

    def test_model_deserialize_okay(self):
        with cosmos:
            s = Schema().deserialize({"type": "cookbook.Recipe"})
            self.assertEqual(s.deserialize("turkey").data, "turkey")

    def test_model_deserialize_bad_name(self):
        with cosmos:
            Schema().deserialize({"type": "cookingbook.Recipe"})
            with self.assertRaisesRegexp(ModelNotFound, "cookingbook.Recipe"):
                cosmos.force()

    def test_subclassing_hook(self):
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Cookie"]))

    def test_recursive_subclassing_hook(self):
        @self.cookbook.model
        class ChocolateCookie(self.cookbook.models.Cookie):
            pass
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Cookie", "ChocolateCookie"]))

    def test_model_illegal_schema(self):
        with self.assertRaises(ValidationError):
            @self.cookbook.model
            class Pizza(object):
                schema = Schema().deserialize({"tipe": "struct"})

    def test_model_schema_validation(self):
        with self.assertRaises(ValidationError):
            self.cookbook.models.Recipe.deserialize_self(1.1)

    def test_model_custom_validation(self):
        with self.assertRaisesRegexp(ValidationError, "kosher"):
            self.cookbook.models.Recipe.deserialize_self("bacon")
        # When not overridden, custom validation passes
        self.cookbook.models.Cookie(True)

    def test_serialize(self):
        self.assertEqual(APISerializer().serialize(self.cookbook), cookbook_spec)

    def test_call(self):
        data = '{"spicy": true}'
        with self.app.test_request_context('/api/actions/cabbage', data=data, content_type="application/json"):
            self.assertEqual(self.cookbook.actions.cabbage(spicy=False), "sauerkraut")

    def test_spec_endpoint(self):
        res = self.werkzeug_client.get('/spec.json')
        self.assertEqual(json.loads(res.data), cookbook_spec)

    def test_schema(self):
        with cosmos:
            APISerializer().deserialize(APISerializer().serialize(self.cookbook))

    def test_load_url(self):
        """Test the API.load function when given a spec URL"""
        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = cookbook_spec
            mock_get.return_value.status_code = 200
            cookbook_decentralized = API.load('http://example.com/spec.json')
            self.assertEqual(APISerializer().serialize(cookbook_decentralized), cookbook_spec)


class TestRemoteAPI(TestCase):

    def setUp(self):
        self.cookbook = APISerializer().deserialize(cookbook_spec)
        self.cookbook.url = 'http://localhost:8881/api'

    def test_remote_no_return_action(self):
        with patch.object(requests, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = None
            self.assertEqual(self.cookbook.actions.noop(), None)
            mock_post.assert_called_with('http://localhost:8881/api/actions/noop', headers={'Content-Type': 'application/json'}, data="")

    def test_properties(self):
        self.assertEqual(self.cookbook.name, "cookbook")
        self.assertEqual(self.cookbook.url, "http://localhost:8881/api")

    def test_models(self):
        self.assertEqual(self.cookbook.models.__all__, ["Cookie", "Recipe"])
        self.assertEqual(Schema().serialize(self.cookbook.models.Recipe.get_schema()), {"type": "string"})

