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
            schema = String

        self.Yay = Yay
        self.cosmos = Cosmos()
        self.cosmos.apis["awesome"] = awesome

    def test_from_json(self):

        lazy = LazyWrapper("awesome.Yay")
        self.assertEqual(lazy._model_cls, None)
        with self.cosmos:
            self.assertEqual(lazy.from_json("Bam").data, "Bam")
            self.assertEqual(lazy._model_cls, self.Yay)
            # By now, _model_cls is set
            self.assertEqual(lazy.from_json("Bam").data, "Bam")

    def test_to_json(self):

        lazy = LazyWrapper("awesome.Yay")
        with self.cosmos:
            self.assertEqual(lazy.to_json(self.Yay("Bam")), "Bam")






