import copy
import json

from unittest2 import TestCase
from werkzeug.wrappers import Response
from werkzeug.test import Client as TestClient

from cosmic.client import WsgiAPIClient, ClientLoggingMixin
from cosmic.globals import cosmos
from cosmic.exceptions import *
from planetarium import *


json_spec = {
    u"name": u"planetarium",
    u"models": {
        u"map": {
            u"Sphere": {
                u"properties": {
                    u"map": {
                        u"name": {
                            u"required": True,
                            u"schema": {u"type": u"String"}
                        },
                        u"temperature": {
                            u"required": True,
                            u"schema": {u"type": u"Float"}
                        },
                    },
                    u"order": [u"name", u"temperature"],
                },
                u"list_metadata": {
                    u"map": {
                        u"last_updated": {
                            u"required": True,
                            u"schema": {u"type": u"DateTime"}
                        },
                    },
                    u"order": [u"last_updated"],

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
                            u"model": u"planetarium.Sphere",
                            u"required": False
                        }
                    },
                    u"order": [u"revolves_around"]
                },
                u'methods': {
                    u'get_by_id': True,
                    u'get_list': True,
                    u'create': True,
                    u'update': True,
                    u'delete': True,
                },
            },
        },
        u"order": [u"Sphere"]
    },
    u"actions": {
        u"map": {
            u"hello": {
                u"accepts": {u"type": u"cosmic.Representation", u"param": u"planetarium.Sphere"},
                u"returns": {u"type": u"String"}
            }
        },
        u"order": [u"hello"]
    }
}


class Retry(Exception):
    pass


class PlanetariumClient(ClientLoggingMixin, WsgiAPIClient):
    token = None
    wsgi_app = planetarium_server.wsgi_app

    def build_request(self, endpoint, *args, **kwargs):
        request = super(PlanetariumClient, self).build_request(endpoint, *args, **kwargs)
        if self.token is not None:
            request.headers["X-Danish"] = self.token
        return request

    def parse_response(self, endpoint, res):
        if res.status_code == 401:
            raise Retry()
        return super(PlanetariumClient, self).parse_response(endpoint, res)

    def call(self, endpoint, *args, **kwargs):
        while True:
            try:
                return super(PlanetariumClient, self).call(endpoint, *args, **kwargs)
            except Retry:
                # Find token, e.g. through OAuth
                self.token = "poppyseed"
                continue

class _LocalRemotePlanetariumTest(TestCase):
    maxDiff = None

    def setUp(self):

        self.local_cosmos = dict(cosmos.items())
        self.remote_cosmos = dict()

        with cosmos.swap(self.remote_cosmos):
            PlanetariumClient()

    def _test(self):
        raise NotImplementedError()

    def _test_logs(self):
        pass

    def test_local(self):
        with cosmos.swap(self.local_cosmos):
            self._test()

    def test_remote(self):
        with cosmos.swap(self.remote_cosmos):
            self._test()
            self._test_logs()


class TestGetById(_LocalRemotePlanetariumTest):

    def _test(self):
        with db.swap(planet_db):
            Sphere = cosmos['planetarium'].models.Sphere
            with self.assertRaises(NotFound):
                Sphere.get_by_id('100')
            rep = Sphere.get_by_id('0')
            self.assertEqual(rep['name'], "Sun")

    def _test_logs(self):

        (req, res) = cosmos['planetarium'].log.pop()

        self.assertEqual(req["method"], "GET")
        self.assertEqual(req["url"], "/Sphere/0")
        self.assertEqual(req["data"], "")

        self.assertEqual(res["status_code"], 200)
        self.assertEqual(dict(res["headers"])["Content-Type"], "application/json")
        self.assertEqual(json.loads(res["data"]), {
            u"name": u"Sun",
            u"temperature": 3000.0,
            "_links": {
                "self": {"href": "/Sphere/0"}
            },
        })

        (req, res) = cosmos['planetarium'].log.pop()

        self.assertEqual(req["method"], "GET")
        self.assertEqual(req["url"], "/Sphere/100")
        self.assertEqual(req["data"], "")
        self.assertEqual(res["status_code"], 404)


class TestCreate(_LocalRemotePlanetariumTest):

    def _test(self):
        with db.swap(copy.deepcopy(planet_db)):
            Sphere = cosmos['planetarium'].models.Sphere

            (id, rep) = Sphere.create(
                name="Pluto",
                revolves_around="0")

            self.assertEqual(id, "3")

            full = {
                "name": "Pluto",
                "temperature": 60,
                "_links": {
                    "self": {"href": "/Sphere/3"},
                    "revolves_around": {"href": "/Sphere/0"},
                }
            }
            self.assertEqual(Representation(Model('planetarium.Sphere')).to_json((id, rep)), full)
            self.assertEqual(db['Sphere']['3'], {
                'name': 'Pluto',
                'temperature': 60,
                'revolves_around': '0',
            })


class TestUpdateLink(_LocalRemotePlanetariumTest):

    def _test(self):
        with db.swap(copy.deepcopy(planet_db)):
            Sphere = cosmos['planetarium'].models.Sphere
            # Save property
            moon = Sphere.get_by_id("2")
            self.assertEqual(moon['revolves_around'], "1")

            rep = Sphere.update("2",
                                name=moon['name'],
                                revolves_around="0")

            self.assertEqual(rep['revolves_around'], "0")
            self.assertEqual(db['Sphere']['2'], {
                'name': moon['name'],
                'temperature': -50,
                'revolves_around': '0',
            })

    def _test_logs(self):

        (req, res) = cosmos['planetarium'].log.pop()

        patch = {
            u'_links': {
                u'self': {u'href': u'/Sphere/2'},
                u'revolves_around': {u'href': u'/Sphere/0'},
            },
            u'name': u'Moon',
        }

        updated = {
            u'_links': {
                u'self': {u'href': u'/Sphere/2'},
                u'revolves_around': {u'href': u'/Sphere/0'},
            },
            u'temperature': -50,
            u'name': u'Moon',
        }

        self.assertEqual(req["method"], "PUT")
        self.assertEqual(req["url"], "/Sphere/2")
        self.assertEqual(json.loads(req["data"]), patch)
        self.assertEqual(dict(req["headers"])["Content-Type"], "application/json")

        self.assertEqual(res["status_code"], 200)
        self.assertEqual(json.loads(res["data"]), updated)
        self.assertEqual(dict(res["headers"])["Content-Type"], "application/json")


class TestUpdateProperty(_LocalRemotePlanetariumTest):

    def _test(self):
        with db.swap(copy.deepcopy(planet_db)):
            Sphere = cosmos['planetarium'].models.Sphere
            moon = Sphere.get_by_id("2")

            rep = Sphere.update("2",
                                name="Luna",
                                revolves_around=moon['revolves_around'])

            self.assertEqual(rep['name'], "Luna")
            self.assertEqual(db['Sphere']['2'], {
                'name': 'Luna',
                'temperature': -50,
                'revolves_around': moon['revolves_around'],
            })

    def _test_logs(self):

        (req, res) = cosmos['planetarium'].log.pop()

        patch = {
            u'_links': {
                u'self': {u'href': u'/Sphere/2'},
                u'revolves_around': {u'href': u'/Sphere/1'},
            },
            u'name': u'Luna',
        }

        updated = {
            u'_links': {
                u'self': {u'href': u'/Sphere/2'},
                u'revolves_around': {u'href': u'/Sphere/1'},
            },
            u'temperature': -50,
            u'name': u'Luna',
        }

        self.assertEqual(req["method"], "PUT")
        self.assertEqual(req["url"], "/Sphere/2")
        self.assertEqual(json.loads(req["data"]), patch)
        self.assertEqual(dict(req["headers"])["Content-Type"], "application/json")

        self.assertEqual(res["status_code"], 200)
        self.assertEqual(json.loads(res["data"]), updated)
        self.assertEqual(dict(res["headers"])["Content-Type"], "application/json")


class TestGetList(_LocalRemotePlanetariumTest):

    def _test(self):
        with db.swap(planet_db):
            Sphere = cosmos['planetarium'].models.Sphere
            res = Sphere.get_list(name="Oops")
            self.assertEqual(len(res[0]), 0)
            res = Sphere.get_list(name="Sun")
            self.assertEqual(len(res[0]), 1)
            self.assertEqual(res[0][0][0], "0")
            res = Sphere.get_list()
            self.assertEqual(len(res[0]), 3)

    def _test_logs(self):

        (req, res) = cosmos['planetarium'].log.pop()

        self.assertEqual(req["method"], "GET")
        self.assertEqual(req["url"], "/Sphere")
        self.assertEqual(req["data"], "")

        self.assertEqual(res["status_code"], 200)
        self.assertEqual(json.loads(res["data"]), {
            "_links": {
                "self": {"href": "/Sphere"}
            },
            "_embedded": {
                "Sphere": [
                    {
                        '_links': {'self': {'href': '/Sphere/0'}},
                        'name': 'Sun',
                        'temperature': 3000.0,
                        },
                    {
                        '_links': {
                            'revolves_around': {'href': '/Sphere/0'},
                            'self': {'href': '/Sphere/1'}
                        },
                        'name': 'Earth',
                        'temperature': 30.0,
                        },
                    {
                        '_links': {
                            'revolves_around': {'href': '/Sphere/1'},
                            'self': {'href': '/Sphere/2'}
                        },
                        'name': 'Moon',
                        'temperature': -50.0,
                        },
                    ]
            },
            'last_updated': '2014-01-01T00:00:00'
        })
        self.assertEqual(dict(res["headers"])["Content-Type"], "application/json")

        (req, res) = cosmos['planetarium'].log.pop()

        url = "/Sphere?name=Sun"
        self.assertEqual(req["method"], "GET")
        self.assertEqual(req["url"], url)
        self.assertEqual(req["data"], "")

        self.assertEqual(res["status_code"], 200)
        self.assertEqual(json.loads(res["data"]), {
            "_links": {
                "self": {"href": "/Sphere?name=Sun"}
            },
            "_embedded": {
                "Sphere": [
                    {
                        '_links': {'self': {'href': '/Sphere/0'}},
                        'name': 'Sun',
                        'temperature': 3000.0,
                        },
                    ]
            },
            'last_updated': '2014-01-01T00:00:00'
        })
        self.assertEqual(dict(res["headers"])["Content-Type"], "application/json")


class TestDelete(_LocalRemotePlanetariumTest):

    def _test(self):
        with db.swap(copy.deepcopy(planet_db)):
            Sphere = cosmos['planetarium'].models.Sphere
            Sphere.delete("1")
            self.assertTrue('1' not in db['Sphere'])
            with self.assertRaises(NotFound):
                Sphere.delete("123811")

    def _test_logs(self):

        (req, res) = cosmos['planetarium'].log.pop()
        self.assertEqual(res["status_code"], 404)

        (req, res) = cosmos['planetarium'].log.pop()

        self.assertEqual(req["method"], "DELETE")
        self.assertEqual(req["url"], "/Sphere/1")
        self.assertEqual(req["data"], "")

        self.assertEqual(res["status_code"], 204)
        self.assertEqual(res["data"], "")


class TestAction(_LocalRemotePlanetariumTest):

    def _test(self):
        pluto = {
            "name": "Pluto",
            "temperature": -120,
        }
        self.assertEqual(cosmos['planetarium'].actions.hello((None, pluto)), "Hello, Pluto")


class TestPlanitarium(TestCase):
    maxDiff = None

    def test_spec_endpoint(self):
        app = planetarium_server.wsgi_app
        client = TestClient(app, response_wrapper=Response)
        res = client.get('/spec.json', headers={'X-Danish': 'poppyseed'})
        self.assertEqual(json.loads(res.data), json_spec)

