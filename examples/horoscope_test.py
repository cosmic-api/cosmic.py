import json
import time
import requests
from mock import patch

from unittest2 import TestCase
from multiprocessing import Process

from cosmic.api import API
from cosmic.tools import CosmicTypeMap
from horoscope import horoscope

def run_horoscope():
    horoscope.run(port=9873)

json_spec = {
    "name": "horoscope",
    "models": [
        {
            "name": "Sign",
            "schema": {"type": "string"}
        }
    ],
    "actions": [
        {
            "name": "predict",
            "accepts": {"type": "horoscope.Sign"},
            "returns": {"type": "string"}
        }
    ]
}

headers = { 'Content-Type': 'application/json' }

class TestTutorialBuildingAPI(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.p = Process(target=run_horoscope)
        cls.p.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.p.terminate()

    def test_run(self):
        res = requests.post('http://localhost:9873/actions/predict', data='"leo"', headers=headers)
        self.assertRegexpMatches(res.json, "handsome stranger")

    def test_spec_endpoint(self):
        res = requests.get('http://localhost:9873/spec.json')
        self.assertEqual(res.json, json_spec)

    def test_wrong_sign(self):
        res = requests.post('http://localhost:9873/actions/predict', data='"tiger"', headers=headers)
        self.assertEqual(res.json, {"error": "Unknown zodiac sign: u'tiger'"})

    def _test_consuming(self):
        h = API.load('http://localhost:9873/spec.json')
        pisces = h.models.Sign("pisces")
        self.assertRegexpMatches(h.actions.predict(pisces), "Stranger yo")


