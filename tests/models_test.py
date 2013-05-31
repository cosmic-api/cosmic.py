from unittest2 import TestCase

from teleport import *

from cosmic.models import *
from cosmic.api import API, ModelSerializer 
from cosmic.actions import Action
from cosmic.exceptions import ModelNotFound


class TestCosmos(TestCase):

    def setUp(self):
        self.cosmos = Cosmos()

    def test_cosmic_types(self):
        self.assertEqual(self.cosmos["cosmic.API"], (API, None,))
        self.assertEqual(self.cosmos["cosmic.Model"], (ModelSerializer, None,))
        self.assertEqual(self.cosmos["cosmic.Action"], (Action, None,))




