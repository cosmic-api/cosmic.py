import json
import time
import requests
from mock import patch

from unittest2 import TestCase

from cosmic.api import API
from cosmic import cosmos
from zodiac import zodiac

json_spec = {
    "name": "zodiac",
    "models": [
        {
            "name": "Sign",
            "schema": {"type": "String"}
        }
    ],
    "actions": {
        "map": {
            u"predict": {
                "accepts": {"type": "zodiac.Sign"},
                "returns": {"type": "String"}
            }
        },
        "order": [u"predict"]
    }
}

class TestTutorialBuildingAPI(TestCase):

    def setUp(self):
        self.c = zodiac.get_flask_app().test_client()
        self.d = zodiac.get_flask_app(debug=True).test_client()

    def test_run(self):
        res = self.c.post('/actions/predict', data='"leo"', content_type="application/json")
        self.assertRegexpMatches(res.data, "handsome stranger")

    def test_spec_endpoint(self):
        res = self.c.get('/spec.json')
        self.assertEqual(json.loads(res.data), json_spec)

    def test_wrong_sign(self):
        res = self.c.post('/actions/predict', data='"tiger"', content_type="application/json")
        self.assertEqual(json.loads(res.data), {"error": "Unknown zodiac sign: u'tiger'"})

    def test_consuming(self):
        with patch.object(requests, 'get') as mock_get:
            mock_get.return_value.json = json_spec
            mock_get.return_value.status_code = 200

            with cosmos:
                h = API.load('http://example.com/spec.json')
                pisces = h.models.Sign("pisces")
                with patch.object(requests, 'post') as mock_post:
                    mock_post.return_value.json = "Yada yada handsome stranger"
                    mock_post.return_value.status_code = 200
                    self.assertRegexpMatches(h.actions.predict(pisces), "handsome stranger")


