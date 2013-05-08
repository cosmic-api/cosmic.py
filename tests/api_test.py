import warnings
import json
import sys

from unittest2 import TestCase
from mock import patch

import requests

from cosmic.exceptions import *
from cosmic.tools import normalize, normalize_schema
from cosmic.api import API, APISerializer
from cosmic.models import *
from cosmic import api, context

from teleport import ValidationError as VError
from teleport import Schema as TSchema

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

        self.cookbook = API.create(u'cookbook')

        @self.cookbook.action(
            accepts=normalize_schema({
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
            returns=normalize_schema({"type": u"json"}))
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
        class Recipe(object):
            schema = normalize_schema({u"type": u"string"})
            @classmethod
            def validate(cls, datum):
                if datum == "bacon":
                    raise ValidationError("Not kosher")

        @self.cookbook.model
        class Cookie(object):
            schema = normalize_schema({u"type": u"boolean"})

        self.app = self.cookbook.get_flask_app(debug=True)
        self.werkzeug_client = self.app.test_client()

    def test_accepts_invalid_schema(self):
        with self.assertRaisesRegexp(VError, "Missing fields"):
            @self.cookbook.action(returns=normalize_schema({"type": "struct"}))
            def func(a, b=1):
                pass

    def test_model_normalize_okay(self):
        self.assertEqual(normalize({"type": "cookbook.Recipe"}, "turkey").data, "turkey")

    def test_model_normalize_bad_api(self):
        with self.assertRaisesRegexp(VError, "Unknown type"):
            normalize({"type": "cookingbook.Recipe"}, "turkey")

    def test_model_normalize_bad_model(self):
        with self.assertRaisesRegexp(VError, "Unknown type"):
            normalize({"type": "cookbook.Schmecipe"}, "turkey")

    def test_subclassing_hook(self):
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Cookie"]))

    def test_recursive_subclassing_hook(self):
        @self.cookbook.model
        class ChocolateCookie(self.cookbook.models.Cookie):
            pass
        self.assertEqual(set(self.cookbook.models.__all__), set(["Recipe", "Cookie", "ChocolateCookie"]))

    def test_model_illegal_schema(self):
        with self.assertRaises(VError):
            @self.cookbook.model
            class Pizza(object):
                schema = normalize_schema({"tipe": "struct"})

    def test_model_schema_validation(self):
        with self.assertRaises(VError):
            self.cookbook.models.Recipe.normalize(1.1)

    def test_model_custom_validation(self):
        with self.assertRaisesRegexp(ValidationError, "kosher"):
            self.cookbook.models.Recipe.normalize("bacon")
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
        normalize({"type": "cosmic.API"}, APISerializer().serialize(self.cookbook))

    def test_load_url(self):
        """Test the API.load function when given a spec URL"""
        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = cookbook_spec
            mock_get.return_value.status_code = 200
            cookbook_decentralized = API.load('http://example.com/spec.json')
            self.assertEqual(APISerializer().serialize(cookbook_decentralized), cookbook_spec)
            self.assertEqual(sys.modules['cosmic.registry.cookbook'], cookbook_decentralized)

    def test_api_module_cache(self):
        self.assertEqual(sys.modules['cosmic.registry.cookbook'], self.cookbook)

    def test_apierror_repr(self):
        """Make sure when APIError gets printed in stack trace we can see the message"""
        try:
            raise APIError("Blah")
        except APIError as e:
            self.assertEqual(unicode(e), "Blah")

class TextContext(TestCase):

    def setUp(self):
        self.cookbook = API.create(u'authenticator')

        @self.cookbook.action(returns=normalize_schema({"type": "string"}))
        def hello():
            return context.secret

        @self.cookbook.context
        def setup(headers):
            if "Password" in headers and headers["Password"] == "crimson":
                return { "secret": "1234" }
            raise AuthenticationError()
            
        self.app = self.cookbook.get_flask_app(debug=True)
        self.werkzeug_client = self.app.test_client()

    def test_fail_authentication(self):
        res = self.werkzeug_client.post('/actions/hello', content_type="application/json")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(json.loads(res.data), {"error": "Authentication failed"})

    def test_successful_authentication(self):
        res = self.werkzeug_client.post('/actions/hello',
            content_type="application/json",
            headers={ 'Password': "crimson" })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data), '1234')


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
        self.assertEqual(TSchema().serialize(self.cookbook.models.Recipe.get_schema()), {"type": "string"})

