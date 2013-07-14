from unittest2 import TestCase

from teleport import *

from cosmic.models import *
from cosmic.actions import Function
from cosmic.api import API, ModelSerializer 
from cosmic.exceptions import ModelNotFound


class TestCosmos(TestCase):

    def setUp(self):
        self.cosmos = Cosmos()

    def test_cosmic_types(self):
        self.assertEqual(self.cosmos["cosmic.API"], (API, None,))
        self.assertEqual(self.cosmos["cosmic.Model"], (ModelSerializer, None,))
        self.assertEqual(self.cosmos["cosmic.Function"], (Function, None,))

class TestLazyWrapper(TestCase):

    def setUp(self):

        awesome = API("awesome")

        @awesome.model
        class Yay(Model):
            properties = [
                required("what", String)
            ]

        self.Yay = Yay
        self.cosmos = Cosmos()
        self.cosmos.apis["awesome"] = awesome

    def test_get_set_data(self):
        y = self.Yay()
        self.assertEqual(y.what, None)
        y.what = "Bam"
        self.assertEqual(y.what, "Bam")

    def test_from_json(self):

        lazy = LazyWrapper("awesome.Yay")
        self.assertEqual(lazy._model_cls, None)
        d = {
            "_links": {
                "self": {"href": "/Yay/123"}
            },
            "what": "Bam"
        }
        with self.cosmos:
            self.assertEqual(lazy.from_json(d).what, "Bam")
            self.assertEqual(lazy._model_cls, self.Yay)
            # By now, _model_cls is set
            self.assertEqual(lazy.from_json(d).what, "Bam")

    def test_to_json(self):

        lazy = LazyWrapper("awesome.Yay")
        d = {
            "_links": {
                "self": {"href": "/Yay/123"}
            },
            "what": "Bam"
        }
        with self.cosmos:
            self.assertEqual(lazy.to_json(self.Yay.from_json(d)), d)






