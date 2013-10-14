from unittest2 import TestCase

import requests
from mock import patch

from werkzeug.exceptions import Unauthorized, BadRequest, InternalServerError
from flask import Flask

from cosmic.models import Cosmos
from cosmic.actions import *
from cosmic.tools import *
from cosmic.http import *

from cosmic.types import *

class TestURLParams(TestCase):

    def setUp(self):

        self.schema = URLParams([
            optional("foo", String),
            required("bars", Array(Integer))
        ])

    def test_okay(self):
        self.assertEqual(self.schema.from_json('foo="Wha"&bars=1'), {
            "foo": "Wha",
            "bars": [1]
        })
        self.assertEqual(self.schema.from_json('foo="Wha"&bars=1&bars=2&bars=3'), {
            "foo": "Wha",
            "bars": [1, 2, 3]
        })
        self.assertEqual(self.schema.from_json('bars=1&bars=2&bars=3'), {
            "bars": [1, 2, 3]
        })

    def test_wrong_deep_type(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid Integer"):
            self.schema.from_json('foo="Wha"&bars=1&bars=1.2')

    def test_unexpected_array(self):
        with self.assertRaises(ValidationError):
            self.schema.from_json('foo="Wha"&bars=1&foo="Bing"')


