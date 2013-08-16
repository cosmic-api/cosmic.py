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

from planetarium import *


json_spec = {
    u"name": u"planetarium",
    u"models": {
        u"map": {
            u"Sphere": {
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
                u"query_fields": {
                    u"map": {
                        u"name": {
                            u"required": False,
                            u"schema": {u"type": u"String"}
                        },
                        u"revolves_around": {
                            u"required": False,
                            u"schema": {u"type": u"String"}
                        }
                    },
                    u"order": [u"name", u"revolves_around"]
                },
                u"links": {
                    u"map": {
                        u"revolves_around": {
                            u"schema": {u"type": u"planetarium.Sphere"},
                            u"required": False
                        }
                    },
                    u"order": [u"revolves_around"]
                },
            },
        },
        u"order": [u"Sphere"]
    },
    u"actions": {
        u"map": {},
        u"order": []
    }
}


class TestPlanitarium(TestCase):

    def setUp(self):
        self.maxDiff = None

        # The planetarium server
        self.cosmos1 = Cosmos()
        # The planetarium client
        self.cosmos2 = Cosmos()

        with self.cosmos1:
            self.planetarium = make_planetarium()

            self.c = self.planetarium.get_flask_app().test_client()
            self.d = self.planetarium.get_flask_app(debug=True).test_client()

        with self.cosmos2:
            with patch.object(requests, 'get') as mock_get:
                mock_get.return_value.json = json_spec
                mock_get.return_value.status_code = 200

                self.remote_planetarium = API.load('http://example.com/spec.json')
                # Use the local API's HTTP client to simulate the remote API's calls
                self.remote_planetarium._request = WerkzeugTestClientPlugin(self.d)


    def test_spec_endpoint(self):
        with self.cosmos1:
            res = self.d.get('/spec.json')
            self.assertEqual(json.loads(res.data), json_spec)


    def _test_follow_links(self):
        with DBContext(planet_db):
            Sphere = cosmos.M('planetarium.Sphere')
            moon = Sphere.get_by_id("2")
            self.assertEqual(moon.name, "Moon")
            self.assertEqual(moon.revolves_around.name, "Earth")
            self.assertEqual(moon.revolves_around.revolves_around.name, "Sun")

    def test_local_follow_links(self):
        with self.cosmos1:
            self._test_follow_links()

    def test_remote_follow_links(self):
        with self.cosmos2:
            self._test_follow_links()


    def _test_get_list(self):
        with DBContext(planet_db):
            Sphere = cosmos.M('planetarium.Sphere')
            res = Sphere.get_list(name="Sun")
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0].id, "0")
            res = Sphere.get_list(name="Oops")
            self.assertEqual(len(res), 0)

    def test_local_get_list(self):
        with self.cosmos1:
            self._test_get_list()

    def test_remote_get_list(self):
        with self.cosmos2:
            self._test_get_list()


    def _test_save_data(self):
        c = copy.deepcopy(planet_db)
        with DBContext(c):
            Sphere = cosmos.M('planetarium.Sphere')
            moon = Sphere.get_by_id("2")
            moon.name = "Luna"
            self.assertEqual(moon.name, "Luna")
            moon.save()
            self.assertEqual(moon.name, "Luna")
            self.assertEqual(c["spheres"][2]["name"], "Luna")

    def test_local_save_data(self):
        with self.cosmos1:
            self._test_save_data()

    def test_remote_save_data(self):
        with self.cosmos2:
            self._test_save_data()


    def _test_create_model(self):
        c = copy.deepcopy(planet_db)
        with DBContext(c):
            Sphere = cosmos.M('planetarium.Sphere')
            pluto = Sphere({
                "name": "Pluto",
                "_links": {
                    "revolves_around": {"href": "/Sphere/0"}
                }
            })
            self.assertEqual(pluto.id, None)
            pluto.save()
            self.assertEqual(pluto.id, "3")

    def test_local_create_model(self):
        with self.cosmos1:
            self._test_create_model()

    def test_remote_create_model(self):
        with self.cosmos2:
            self._test_create_model()


    def _test_delete(self):
        c = copy.deepcopy(planet_db)
        with DBContext(c):
            Sphere = cosmos.M('planetarium.Sphere')
            earth = Sphere.get_by_id("1")
            earth.delete()
            self.assertEqual(c["spheres"][1], None)

    def test_local_delete(self):
        with self.cosmos1:
            self._test_delete()

    def test_remote_delete(self):
        with self.cosmos2:
            self._test_delete()


