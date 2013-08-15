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
        self.c = planetarium.get_flask_app().test_client()
        self.d = planetarium.get_flask_app(debug=True).test_client()

    def test_spec_endpoint(self):
        res = self.d.get('/spec.json')
        self.assertEqual(json.loads(res.data), json_spec)

