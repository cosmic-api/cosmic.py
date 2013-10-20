from unittest2 import TestCase

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
        self.assertEqual(API.to_json(self.places), {
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
        with self.cosmos:
            sesame31 = self.places.models.Address(number=31, street="Sesame")

            self.assertEqual(sesame31.number, 31)
            self.assertEqual(sesame31.street, "Sesame")

    def test_serialize_model(self):
        with self.cosmos:
            sesame31 = self.places.models.Address(number=31, street="Sesame")

            self.assertEqual(self.places.models.Address.to_json(sesame31), {
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
        with self.cosmos:
            toronto = self.places.models.City(name="Toronto")
            spadina147 = self.places.models.Address(
                number=147,
                street="Spadina",
                city=toronto)

            self.assertEqual(spadina147.city.name, "Toronto")
            self.assertEqual(spadina147.id is None, True)


