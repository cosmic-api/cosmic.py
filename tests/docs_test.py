from unittest2 import TestCase

from cosmic.models import BaseModel
from cosmic.globals import cosmos
from cosmic.http import *
from cosmic.api import API
from cosmic.client import WsgiAPIClient
from cosmic.types import *


class TestGuideWhatIsAPI(TestCase):
    maxDiff = None

    def setUp(self):
        self.cosmos = {}
        with cosmos.scope(self.cosmos):
            self.mathy = API("trivia", homepage="http://example.com")

    def test_to_json(self):
        with cosmos.scope(self.cosmos):
            self.assertEqual(APISpec.to_json(self.mathy.spec), {
                u'name': 'trivia',
                u'homepage': 'http://example.com',
                u'actions': {u'map': {}, u'order': []},
                u'models': {u'map': {}, u'order': []}
            })


class TestGuideModels(TestCase):
    maxDiff = None

    def setUp(self):
        self.cosmos = {}
        with cosmos.scope(self.cosmos):
            self.places = places = API('places')

            @places.model
            class Address(BaseModel):
                properties = [
                    required(u"number", Integer),
                    required(u"street", String),
                    optional(u"city", String)
                ]

    def test_to_json(self):
        places = self.places
        with cosmos.scope(self.cosmos):
            self.assertEqual(APISpec.to_json(places.spec), {
                u'name': u'places',
                u'actions': {u'map': {}, u'order': []},
                u"models": {
                    u"map": {
                        u"Address": {
                            u"properties": {
                                u"map": {
                                    u"number": {
                                        u"required": True,
                                        u"schema": {u"type": u"Integer"}
                                    },
                                    u"street": {
                                        u"required": True,
                                        u"schema": {u"type": u"String"}
                                    },
                                    u"city": {
                                        u"required": False,
                                        u"schema": {u"type": u"String"}
                                    }
                                },
                                u"order": [u"number", u"street", u"city"]
                            },
                            u"links": {u"map": {}, u"order": []},
                            u"query_fields": {u"map": {}, u"order": []},
                            u"list_metadata": {u"map": {}, u"order": []},
                            u'methods': {
                                u'get_by_id': False,
                                u'get_list': False,
                                u'create': False,
                                u'update': False,
                                u'delete': False,
                            },
                        }
                    },
                    u"order": [u"Address"]
                }
            })

    def test_serialize_model(self):
        places = self.places
        with cosmos.scope(self.cosmos):
            rep = {
                "number": 31,
                "street": "Sesame"
            }

            self.assertEqual(Representation(Model('places.Address')).to_json((None, rep)), rep)


class TestGuideModelLinks(TestCase):
    maxDiff = None

    def setUp(self):
        self.cosmos1 = {}
        with cosmos.scope(self.cosmos1):
            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                properties = [
                    optional(u"name", String)
                ]

            @places.model
            class Address(BaseModel):
                properties = [
                    required(u"number", Integer),
                    required(u"street", String),
                ]
                links = [
                    required_link(u"city", Model('places.City'))
                ]

        self.cosmos2 = {}
        with cosmos.scope(self.cosmos2):

            class PlacesClient(WsgiAPIClient):
                wsgi_app = Server(places).wsgi_app

            self.remote_places = PlacesClient()

    def remote_create_models(self):
        with cosmos.scope(self.cosmos2):
            elm13 = self.remote_places.models.Address(number=13, street="Elm")
            self.assertEqual(elm13.number, 13)


class TestGuideGetById(TestCase):
    maxDiff = None

    def setUp(self):
        self.cosmos = {}
        with cosmos.scope(self.cosmos):

            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                properties = [
                    optional(u"name", String)
                ]

                @classmethod
                def get_by_id(cls, id):
                    if id in cities:
                        return cities[id]
                    else:
                        return None

            cities = {
                "0": {"name": "Toronto"},
                "1": {"name": "San Francisco"},
            }

    def test_access_links(self):
        places = self.places
        with cosmos.scope(self.cosmos):
            city = places.models.City.get_by_id("0")
            self.assertEqual(city['name'], "Toronto")
            self.assertEqual(places.models.City.get_by_id("5") is None, True)


class TestGuideSave(TestCase):
    maxDiff = None

    def setUp(self):
        self.cosmos = {}
        with cosmos.scope(self.cosmos):
            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                methods = ["create", "update"]
                properties = [
                    optional(u"name", String)
                ]

                @classmethod
                def validate_patch(cls, datum):
                    if datum[u"name"][0].islower():
                        raise ValidationError("Name must be capitalized", datum["name"])

                @classmethod
                def create(cls, **patch):
                    id = str(len(cities))
                    cities[id] = patch
                    return id, patch

                @classmethod
                def update(cls, id, **patch):
                    cities[id] = patch
                    return patch

        self.cosmos2 = {}
        with cosmos.scope(self.cosmos2):

            class PlacesClient(WsgiAPIClient):
                wsgi_app = Server(places).wsgi_app
                server_cosmos = self.cosmos

            self.remote_places = PlacesClient()

        cities = {
            "0": {"name": "Toronto"},
            "1": {"name": "San Francisco"},
        }

    def test_save_good(self):
        places = self.places
        with cosmos.scope(self.cosmos):
            (id, rep) = places.models.City.create(name="Moscow")
            self.assertEqual(id, "2")

    def test_local_save_validation_error(self):
        with cosmos.scope(self.cosmos):
            with self.assertRaisesRegexp(ValidationError, "must be capitalized"):
                self.places.models.City.validate_patch({"name": "moscow"})
                self.places.models.City.create(name="moscow")

    def test_remote_save_validation_error(self):
        with cosmos.scope(self.cosmos2):
            with self.assertRaisesRegexp(RemoteHTTPError, "must be capitalized"):
                self.remote_places.models.City.create(name="moscow")


class TestGuideDelete(TestCase):
    maxDiff = None

    def setUp(self):
        self.cosmos = {}
        with cosmos.scope(self.cosmos):
            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                methods = ["get_by_id", "delete"]
                properties = [
                    optional(u"name", String)
                ]

                @classmethod
                def get_by_id(cls, id):
                    if id in cities:
                        return cities[id]
                    raise NotFound

                @classmethod
                def delete(cls, id):
                    del cities[id]

            cities = {
                "0": {"name": "Toronto"},
                "1": {"name": "San Francisco"},
            }

    def test_save(self):
        places = self.places
        with cosmos.scope(self.cosmos):
            city = places.models.City.get_by_id("0")
            places.models.City.delete("0")
            with self.assertRaises(NotFound):
                places.models.City.get_by_id("0")


class TestGuideGetList(TestCase):
    maxDiff = None

    def setUp(self):

        self.cosmos = {}
        with cosmos.scope(self.cosmos):

            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                properties = [
                    optional(u"name", String)
                ]
                query_fiels = [
                    optional(u"country", String)
                ]

                @classmethod
                def get_list(cls, country=None):
                    if country is None:
                        return cities.items()
                    elif country == "Canada":
                        return [("0", cities["0"])]
                    elif country == "USA":
                        return [("1", cities["1"])]
                    else:
                        return []

            cities = {
                "0": {"name": "Toronto"},
                "1": {"name": "San Francisco"},
            }

    def test_get_list(self):
        places = self.places
        with cosmos.scope(self.cosmos):
            l1 = places.models.City.get_list()
            self.assertEqual(len(l1), 2)
            l2 = places.models.City.get_list(country="Canada")
            self.assertEqual(len(l2), 1)
            self.assertEqual(l2[0][1]['name'], "Toronto")
            l3 = places.models.City.get_list(country="Russia")
            self.assertEqual(l3, [])


class TestGuideAction(TestCase):
    maxDiff = None

    def setUp(self):
        self.cosmos1 = {}
        with cosmos.scope(self.cosmos1):
            self.mathy = mathy = API("mathy")

            @mathy.action(accepts=Array(Integer), returns=Integer)
            def add(numbers):
                return sum(numbers)

            @mathy.action(accepts=Struct([
                required(u'numerator', Integer),
                required(u'denominator', Integer),
            ]), returns=Integer)
            def divide(numerator, denominator):
                return numerator / denominator


            self.add = add

        self.cosmos2 = {}
        with cosmos.scope(self.cosmos2):

            class MathyClient(WsgiAPIClient):
                wsgi_app = Server(mathy).wsgi_app

            self.remote_mathy = MathyClient()

    def test_call_as_function(self):
        self.assertEqual(self.add([1, 2, 3]), 6)

    def test_call_as_action(self):
        self.assertEqual(self.mathy.actions.add([1, 2, 3]), 6)

    def test_call_as_action_remote(self):
        self.assertEqual(self.remote_mathy.actions.add([1, 2, 3]), 6)

    def test_call_as_action_remote_kwargs(self):
        self.assertEqual(self.remote_mathy.actions.divide(numerator=10, denominator=5), 2)

    def test_remote_action_validation_error(self):
        with self.assertRaisesRegexp(HTTPError, "Invalid Integer"):
            self.remote_mathy.actions.add([1, 2, True])
