from unittest2 import TestCase

from teleport import *

from cosmic.models import *
from cosmic.api import APISerializer, ModelSerializer 
from cosmic.actions import ActionSerializer 
from cosmic.exceptions import ModelNotFound


class TestCosmos(TestCase):

    def setUp(self):
        self.cosmos = Cosmos()

    def test_cosmic_types(self):
        self.assertEqual(self.cosmos["cosmic.API"], APISerializer)
        self.assertEqual(self.cosmos["cosmic.Model"], ModelSerializer)
        self.assertEqual(self.cosmos["cosmic.Action"], ActionSerializer)




