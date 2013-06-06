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
from cosmic.models import Model, LazyWrapper
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
                u'returns': {u'type': u'JSON'},
                u'doc': "Yay cabbage"
            },
            u'noop': {}
        },
        u'order': [u'cabbage', u'noop']
    },
    u"models": [
        {
            u"name": u"Recipe",
            u"schema": {u"type": u"String"}
        },
        {
            u"name": u"Cookie",
            u"schema": {u"type": u"Boolean"}
        }
    ]
}



class TestAPI(TestCase):

    def setUp(self):
        self.maxDiff = None

        self.cookbook = API(u'cookbook')

        @self.cookbook.action(
            accepts=Struct([
                required(u"spicy", Boolean),
                optional(u"capitalize", Boolean)
            ]),
            returns=JSON,
            doc=u"Yay cabbage")
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
            schema = String

            @classmethod
            def assemble(cls, datum):
                if datum == "bacon":
                    raise ValidationError("Not kosher")
                return cls(datum)

        @self.cookbook.model
        class Cookie(Model):
            schema = Boolean

        self.app_debug = self.cookbook.get_flask_app(debug=True)
        self.client_debug = self.app_debug.test_client()

        self.app = self.cookbook.get_flask_app()
        self.client = self.app.test_client()

    def test_model(self):
        R = self.cookbook.models.Recipe
        with cosmos:
            self.assertEqual(Schema.to_json(R), {"type": "cookbook.Recipe"})
            pancake = R.from_json("pancake")
            self.assertEqual(pancake.data, u"pancake")
            self.assertEqual(R.to_json(pancake), u"pancake")

    def test_LazyWrapper_okay(self):
        ls = LazyWrapper("cookbook.Recipe")
        with cosmos:
            self.assertEqual(Schema.to_json(ls), {"type": "cookbook.Recipe"})
            # This time model_cls should be cached
            self.assertEqual(Schema.to_json(ls), {"type": "cookbook.Recipe"})

    def test_LazyWrapper_fail(self):
        ls = LazyWrapper("unknown.Unknown")
        with self.assertRaises(ModelNotFound):
            ls.from_json(1)

    # TODO: Teleport should raise a ValidationError here
    def _test_accepts_invalid_schema(self):
        with self.assertRaisesRegexp(ValidationError, "Missing fields"):
            @self.cookbook.action(returns=Schema.from_json({"type": "Struct"}))
            def func(a, b=1):
                pass

    def test_model_deserialize_okay(self):
        with cosmos:
            s = Schema.from_json({"type": "cookbook.Recipe"})
            self.assertEqual(s.from_json("turkey").data, "turkey")

    def test_model_deserialize_bad_name(self):
        with cosmos:
            Schema.from_json({"type": "cookingbook.Recipe"})
            with self.assertRaisesRegexp(ModelNotFound, "cookingbook.Recipe"):
                cosmos.force()

    def test_subclassing_hook(self):
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Cookie"]))

    def test_recursive_subclassing_hook(self):
        @self.cookbook.model
        class ChocolateCookie(self.cookbook.models.Cookie):
            pass
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Cookie", "ChocolateCookie"]))

    def test_model_schema_validation(self):
        with self.assertRaises(ValidationError):
            self.cookbook.models.Recipe.from_json(1.1)

    def test_model_custom_validation(self):
        with self.assertRaisesRegexp(ValidationError, "kosher"):
            self.cookbook.models.Recipe.from_json("bacon")
        # When not overridden, custom validation passes
        self.cookbook.models.Cookie(True)

    def test_serialize(self):
        self.assertEqual(API.to_json(self.cookbook), cookbook_spec)

    def test_call(self):
        data = '{"spicy": true}'
        self.assertEqual(self.cookbook.actions.cabbage(spicy=False), "sauerkraut")

    def test_spec_endpoint(self):
        res = self.client.get('/spec.json')
        self.assertEqual(json.loads(res.data), cookbook_spec)

    def test_spec_wrong_method(self):
        res = self.client.get('/actions/noop')
        self.assertEqual(res.status_code, 405)
        res = self.client.post('/spec.json')
        self.assertEqual(res.status_code, 405)

    def test_spec_wrong_content_type(self):
        res = self.client.post('/actions/noop')
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Content-Type")
        res = self.client.post('/actions/noop', content_type="application/xml")
        self.assertEqual(res.status_code, 400)
        self.assertRegexpMatches(res.data, "Content-Type")

    def test_schema(self):
        with cosmos:
            API.from_json(API.to_json(self.cookbook))

    def test_load_url(self):
        """Test the API.load function when given a spec URL"""
        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = cookbook_spec
            mock_get.return_value.status_code = 200
            cookbook_decentralized = API.load('http://example.com/spec.json')
            self.assertEqual(API.to_json(cookbook_decentralized), cookbook_spec)


class TestRemoteAPI(TestCase):

    def setUp(self):
        self.cookbook = API.from_json(cookbook_spec)
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
        self.assertEqual(self.cookbook.models.__all__, ["Recipe", "Cookie"])
        self.assertEqual(Schema.to_json(self.cookbook.models.Recipe.schema), {"type": "String"})

