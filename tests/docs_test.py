from unittest2 import TestCase
from mock import patch

from cosmic.models import Cosmos, BaseModel
from cosmic.actions import *
from cosmic.tools import *
from cosmic.http import *
from cosmic.api import API

from cosmic.types import *

class TestGuideModels(TestCase):
    maxDiff = None

    def setUp(self):

        self.cosmos = Cosmos()
        with self.cosmos:

            self.places = places = API('places')

            @places.model
            class Address(BaseModel):
                properties = [
                    required("number", Integer),
                    required("street", String),
                    optional("city", String)
                ]

    def test_to_json(self):
        places = self.places
        with self.cosmos:
            self.assertEqual(API.to_json(places), {
                u'name': u'places',
                u'actions': { u'map': {}, u'order': [] },
                u"models": {
                    u"map": {
                        u"Address": {
                            u"data_schema": {
                                u'type': u"Struct",
                                u"param": {
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
                                }
                            },
                            u"links": { u"map": {}, u"order": [] },
                            u"query_fields": { u"map": {}, u"order": [] }
                        }
                    },
                    u"order": [u"Address"]
                }
            })

    def test_access_attributes(self):
        places = self.places
        with self.cosmos:
            sesame31 = places.models.Address(number=31, street="Sesame")

            self.assertEqual(sesame31.number, 31)
            self.assertEqual(sesame31.street, "Sesame")

    def test_serialize_model(self):
        places = self.places
        with self.cosmos:
            sesame31 = places.models.Address(number=31, street="Sesame")

            self.assertEqual(places.models.Address.to_json(sesame31), {
                u"number": 31,
                u"street": "Sesame"
            })


class TestGuideModelLinks(TestCase):
    maxDiff = None

    def setUp(self):

        self.cosmos = Cosmos()
        with self.cosmos:

            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                properties = [
                    optional("name", String)
                ]

            @places.model
            class Address(BaseModel):
                properties = [
                    required("number", Integer),
                    required("street", String),
                ]
                links = [
                    required("city", City)
                ]

    def test_access_links(self):
        places = self.places
        with self.cosmos:
            toronto = places.models.City(name="Toronto")
            spadina147 = places.models.Address(
                number=147,
                street="Spadina",
                city=toronto)

            self.assertEqual(spadina147.city.name, "Toronto")
            self.assertEqual(spadina147.id is None, True)


class TestGuideGetById(TestCase):
    maxDiff = None

    def setUp(self):
        self.cosmos = Cosmos()
        with self.cosmos:

            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                properties = [
                    optional("name", String)
                ]

                @classmethod
                def get_by_id(cls, id):
                    if id in cities:
                        return cities[id]
                    else:
                        return None

            cities = {
                "0": City(name="Toronto", id="0"),
                "1": City(name="San Francisco", id="1"),
            }

    def test_access_links(self):
        places = self.places
        with self.cosmos:
            city = places.models.City.get_by_id("0")
            self.assertEqual(city.name, "Toronto")
            self.assertEqual(places.models.City.get_by_id("5") is None, True)

class TestGuideSave(TestCase):
    maxDiff = None

    def setUp(self):

        self.cosmos = Cosmos()
        with self.cosmos:

            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                properties = [
                    optional("name", String)
                ]

                def save(self):
                    if self.id is None:
                        # Create new id
                        self.id = str(len(cities))
                    cities[self.id] = self

            cities = {
                "0": City(name="Toronto", id="0"),
                "1": City(name="San Francisco", id="1"),
            }

    def test_save(self):
        places = self.places
        with self.cosmos:
            city = places.models.City(name="Moscow")
            self.assertEqual(city.id is None, True)
            city.save()
            self.assertEqual(city.id, "2")

class TestGuideDelete(TestCase):
    maxDiff = None

    def setUp(self):

        self.cosmos = Cosmos()
        with self.cosmos:

            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                properties = [
                    optional("name", String)
                ]

                @classmethod
                def get_by_id(cls, id):
                    if id in cities:
                        city = cities[id]
                        city.id = id
                        return city
                    else:
                        return None

                def delete(self):
                    del cities[self.id]

            cities = {
                "0": City(name="Toronto", id="0"),
                "1": City(name="San Francisco", id="1"),
            }

    def test_save(self):
        places = self.places
        with self.cosmos:
            city = places.models.City.get_by_id("0")
            city.delete()
            self.assertEqual(places.models.City.get_by_id("0") is None, True)


class TestGuideGetList(TestCase):
    maxDiff = None

    def setUp(self):

        self.cosmos = Cosmos()
        with self.cosmos:

            self.places = places = API('places')

            @places.model
            class City(BaseModel):
                properties = [
                    optional("name", String)
                ]
                query_fiels = [
                    optional("country", String)
                ]

                @classmethod
                def get_list(cls, country=None):
                    if country is None:
                        return cities.values()
                    elif country == "Canada":
                        return [cities["0"]]
                    elif country == "USA":
                        return [cities["1"]]
                    else:
                        return []

            cities = {
                "0": City(name="Toronto", id="0"),
                "1": City(name="San Francisco", id="1"),
            }

    def test_get_list(self):
        places = self.places
        with self.cosmos:
            l1 = places.models.City.get_list()
            self.assertEqual(len(l1), 2)
            l2 = places.models.City.get_list(country="Canada")
            self.assertEqual(len(l2), 1)
            self.assertEqual(l2[0].name, "Toronto")
            l3 = places.models.City.get_list(country="Russia")
            self.assertEqual(l3, [])


class TestGuideAction(TestCase):
    maxDiff = None

    def setUp(self):

        self.cosmos1 = Cosmos()
        with self.cosmos1:

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

        self.cosmos2 = Cosmos()
        with self.cosmos2:
            with patch.object(requests, 'get') as mock_get:
                mock_get.return_value.json = lambda: API.to_json(mathy)
                mock_get.return_value.status_code = 200
                self.remote_mathy = API.load('http://example.com/spec.json')
                self.remote_mathy.client_hook = WerkzeugTestClientHook(mathy.get_flask_app().test_client())

    def test_call_as_function(self):
        self.assertEqual(self.add([1, 2, 3]), 6)

    def test_call_as_action(self):
        self.assertEqual(self.mathy.actions.add([1, 2, 3]), 6)

    def test_call_as_action_remote(self):
        self.assertEqual(self.remote_mathy.actions.add([1, 2, 3]), 6)

    def test_call_as_action_remote_kwargs(self):
        self.assertEqual(self.remote_mathy.actions.divide(numerator=10, denominator=5), 2)

    def test_remote_action_validation_error(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid Integer"):
            self.remote_mathy.actions.add([1, 2, True])
