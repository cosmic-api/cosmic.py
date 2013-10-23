import json
import time
import copy
import requests

from mock import patch

from unittest2 import TestCase

from cosmic.api import API
from cosmic.http import WerkzeugTestClientHook, SaveStackClientHookMixin
from cosmic import cosmos
from cosmic.testing import DBContext
from cosmic.models import Cosmos, M

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
    "actions": {
        "map": {
            u"hello": {
                "accepts": {"type": "planetarium.Sphere"},
                "returns": {"type": "String"}
            }
        },
        "order": [u"hello"]
    }
}


class TestPlanitarium(TestCase):

    def setUp(self):
        self.maxDiff = None

        self.cosmos1 = cosmos.clone()
        self.cosmos2 = Cosmos()

        with self.cosmos1:
            self.planetarium = planetarium

            self.c = self.planetarium.get_flask_app().test_client()
            app = self.planetarium.get_flask_app()
            app.debug = True
            self.d = app.test_client()

        with self.cosmos2:
            with patch.object(requests, 'get') as mock_get:
                mock_get.return_value.json = lambda: json_spec
                mock_get.return_value.status_code = 200

                self.remote_planetarium = API.load('http://example.com/spec.json')

                class Retry(Exception):
                    pass

                class Hook(SaveStackClientHookMixin, WerkzeugTestClientHook):
                    token = None

                    def build_request(self, endpoint, *args, **kwargs):
                        request = super(Hook, self).build_request(endpoint, *args, **kwargs)
                        if self.token is not None:
                            request.headers["X-Danish"] = self.token
                        return request

                    def parse_response(self, endpoint, res):
                        if res.status_code == 401:
                            raise Retry()
                        return super(Hook, self).parse_response(endpoint, res)

                    def call(self, endpoint, *args, **kwargs):
                        while True:
                            try:
                                return super(Hook, self).call(endpoint, *args, **kwargs)
                            except Retry:
                                # Find token, e.g. through OAuth
                                self.token = "poppyseed"
                                continue

                # Use the local API's HTTP client to simulate the remote API's calls
                self.remote_planetarium.client_hook = Hook(self.d)

    def test_guess_methods(self):
        with self.cosmos1:
            all_methods = set(['get_list', 'get_by_id', 'create', 'update', 'delete'])
            self.assertEqual(set(M('planetarium.Sphere').methods), all_methods)

    def test_spec_endpoint(self):
        with self.cosmos1:
            res = self.d.get('/spec.json')
            self.assertEqual(json.loads(res.data), json_spec)

    def test_envelope_endpoint(self):
        with self.cosmos1:
            c = copy.deepcopy(planet_db)
            with DBContext(c):
                Sphere = M('planetarium.Sphere')
                res = self.d.post('/envelope', content_type="application/json", data=json.dumps({
                    "method": "POST",
                    "url": "/Sphere",
                    "headers": [
                        {
                            "name": "Content-Type",
                            "value": "application/json"
                        },
                        {
                            "name": "X-Danish",
                            "value": "poppyseed"
                        }
                    ],
                    "body": json.dumps({
                        "name": "Saturn"
                    })
                }))
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.headers["Content-Type"], "application/json")
                body = json.loads(res.data)
                self.assertEqual(body["code"], 201)
                self.assertTrue({
                    "name": "Content-Type",
                    "value": "application/json"
                } in body["headers"])
                self.assertTrue({
                    "name": "Location",
                    "value": "/Sphere/3"
                } in body["headers"])
                self.assertEqual(json.loads(body["body"]), {
                    "name": "Saturn",
                    "_links": {
                        "self": {"href": "/Sphere/3"}
                    }
                })

    def test_local_call_action(self):
        pluto = self.planetarium.models.Sphere(name="Pluto")
        self.assertEqual(self.planetarium.actions.hello(pluto), "Hello, Pluto")

    def test_remote_call_action(self):
        pluto = self.remote_planetarium.models.Sphere(name="Pluto")
        self.assertEqual(self.remote_planetarium.actions.hello(pluto), "Hello, Pluto")

    def _test_follow_links(self):
        with DBContext(planet_db):
            Sphere = M('planetarium.Sphere')
            moon = Sphere.get_by_id("2")
            self.assertEqual(Sphere.get_by_id("5"), None)
            self.assertEqual(moon.name, "Moon")
            self.assertEqual(moon.revolves_around.name, "Earth")
            self.assertEqual(moon.revolves_around.revolves_around.name, "Sun")

    def test_local_follow_links(self):
        with self.cosmos1:
            self._test_follow_links()

    def test_remote_follow_links(self):
        with self.cosmos2:
            self._test_follow_links()

            (req, res) = self.remote_planetarium.client_hook.stack.pop()

            self.assertEqual(req["method"], "GET")
            self.assertEqual(req["url"], "/Sphere/0")
            self.assertEqual(req["data"], "")

            self.assertEqual(res["status_code"], 200)
            self.assertEqual(json.loads(res["data"]), planet_db['Sphere'][0])
            self.assertEqual(res["headers"]["Content-Type"], "application/json")

    def test_local_str_model(self):
        m = self.planetarium.models.Sphere(name="Neptune")
        self.assertRegexpMatches(str(m), 'examples.planetarium.Sphere object at')

    def test_remote_str_model(self):
        m = self.remote_planetarium.models.Sphere(name="Neptune")
        self.assertRegexpMatches(str(m), 'cosmic.api.Sphere object at')


    def _test_get_list(self):
        with DBContext(planet_db):
            Sphere = M('planetarium.Sphere')
            res = Sphere.get_list(name="Oops")
            self.assertEqual(len(res), 0)
            res = Sphere.get_list(name="Sun")
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0].id, "0")
            res = Sphere.get_list()
            self.assertEqual(len(res), 3)

    def test_local_get_list(self):
        with self.cosmos1:
            self._test_get_list()

    def test_remote_get_list(self):
        with self.cosmos2:
            self._test_get_list()

            (req, res) = self.remote_planetarium.client_hook.stack.pop()

            self.assertEqual(req["method"], "GET")
            self.assertEqual(req["url"], "/Sphere")
            self.assertEqual(req["data"], "")

            self.assertEqual(res["status_code"], 200)
            self.assertEqual(json.loads(res["data"]), {
                "_links": {
                    "self": {"href": "/Sphere"}
                },
                "_embedded": {
                    "Sphere": planet_db['Sphere']
                }
            })
            self.assertEqual(res["headers"]["Content-Type"], "application/json")

            (req, res) = self.remote_planetarium.client_hook.stack.pop()

            url = "/Sphere?name=Sun"
            self.assertEqual(req["method"], "GET")
            self.assertEqual(req["url"], url)
            self.assertEqual(req["data"], "")

            self.assertEqual(res["status_code"], 200)
            self.assertEqual(json.loads(res["data"]), {
                "_links": {
                    "self": {"href": url}
                },
                "_embedded": {
                    "Sphere": [planet_db['Sphere'][0]]
                }
            })
            self.assertEqual(res["headers"]["Content-Type"], "application/json")


    def _test_save_property(self):
        c = copy.deepcopy(planet_db)
        with DBContext(c):
            Sphere = M('planetarium.Sphere')
            moon = Sphere.get_by_id("2")
            moon.name = "Luna"
            self.assertEqual(moon.name, "Luna")
            moon.save()
            self.assertEqual(moon.name, "Luna")
            self.assertEqual(c['Sphere'][2]["name"], "Luna")

    def test_local_save_property(self):
        with self.cosmos1:
            self._test_save_property()

    def test_remote_save_property(self):
        with self.cosmos2:
            self._test_save_property()

            (req, res) = self.remote_planetarium.client_hook.stack.pop()

            updated = {
                u'_links': {
                    u'self': {u'href': u'/Sphere/2'},
                    u'revolves_around': {u'href': u'/Sphere/1'}
                },
                u'name': u'Luna'
            }

            self.assertEqual(req["method"], "PUT")
            self.assertEqual(req["url"], "/Sphere/2")
            self.assertEqual(json.loads(req["data"]), updated)
            self.assertEqual(req["headers"]["Content-Type"], "application/json")

            self.assertEqual(res["status_code"], 200)
            self.assertEqual(json.loads(res["data"]), updated)
            self.assertEqual(res["headers"]["Content-Type"], "application/json")


    def _test_save_link(self):
        c = copy.deepcopy(planet_db)
        with DBContext(c):
            Sphere = M('planetarium.Sphere')
            # Save property
            moon = Sphere.get_by_id("2")
            self.assertEqual(moon.revolves_around.id, "1")
            moon.revolves_around = Sphere.get_by_id("0")
            moon.save()
            self.assertEqual(moon.revolves_around.id, "0")
            self.assertEqual(c['Sphere'][2]["_links"]["revolves_around"]["href"], "/Sphere/0")

    def test_local_save_link(self):
        with self.cosmos1:
            self._test_save_link()

    def test_remote_save_link(self):
        with self.cosmos2:
            self._test_save_link()

            (req, res) = self.remote_planetarium.client_hook.stack.pop()

            updated = {
                u'_links': {
                    u'self': {u'href': u'/Sphere/2'},
                    u'revolves_around': {u'href': u'/Sphere/0'}
                },
                u'name': u'Moon'
            }

            self.assertEqual(req["method"], "PUT")
            self.assertEqual(req["url"], "/Sphere/2")
            self.assertEqual(json.loads(req["data"]), updated)
            self.assertEqual(req["headers"]["Content-Type"], "application/json")

            self.assertEqual(res["status_code"], 200)
            self.assertEqual(json.loads(res["data"]), updated)
            self.assertEqual(res["headers"]["Content-Type"], "application/json")


    def _test_create_model(self):
        c = copy.deepcopy(planet_db)
        with DBContext(c):
            Sphere = M('planetarium.Sphere')
            pluto = Sphere(
                name="Pluto",
                revolves_around=Sphere(id="0"))
            self.assertEqual(pluto.id, None)
            self.assertEqual(Sphere.to_json(pluto), {
                "name": "Pluto",
                "_links": {
                    "revolves_around": {"href": "/Sphere/0"}
                }
            })
            pluto.save()
            self.assertEqual(pluto.id, "3")
            full = {
                "name": "Pluto",
                "_links": {
                    "self": {"href": "/Sphere/3"},
                    "revolves_around": {"href": "/Sphere/0"}
                }
            }
            self.assertEqual(Sphere.to_json(pluto), full)
            self.assertEqual(c['Sphere'][3], full)

    def test_local_create_model(self):
        with self.cosmos1:
            self._test_create_model()

    def test_remote_create_model(self):
        with self.cosmos2:
            self._test_create_model()


    def _test_delete(self):
        c = copy.deepcopy(planet_db)
        with DBContext(c):
            Sphere = M('planetarium.Sphere')
            earth = Sphere.get_by_id("1")
            earth.delete()
            self.assertEqual(c['Sphere'][1], None)

    def test_local_delete(self):
        with self.cosmos1:
            self._test_delete()

    def test_remote_delete(self):
        with self.cosmos2:
            self._test_delete()

            (req, res) = self.remote_planetarium.client_hook.stack.pop()

            self.assertEqual(req["method"], "DELETE")
            self.assertEqual(req["url"], "/Sphere/1")
            self.assertEqual(req["data"], "")

            self.assertEqual(res["status_code"], 204)
            self.assertEqual(res["data"], "")

    def test_not_found(self):
        with self.cosmos1:
            with DBContext(planet_db):
                res = self.d.get('/Sphere/4', headers={"X-Danish": "poppyseed"})
                self.assertEqual(res.status_code, 404)




