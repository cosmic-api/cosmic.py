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
