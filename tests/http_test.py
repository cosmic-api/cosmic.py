from datetime import datetime

from unittest2 import TestCase

from cosmic.types import *


class TestURLParams(TestCase):
    def setUp(self):
        self.schema = URLParams([
            optional("foo", String),
            required("bars", Array(Integer))
        ])

    def test_okay(self):
        self.assertEqual(self.schema.from_json('foo=Wha&bars=[1]'), {
            "foo": "Wha",
            "bars": [1]
        })
        self.assertEqual(self.schema.from_json('foo=Wha&bars=[1,2,3]'), {
            "foo": "Wha",
            "bars": [1, 2, 3]
        })
        self.assertEqual(self.schema.from_json('bars=[1,2,3]'), {
            "bars": [1, 2, 3]
        })

    def test_string_wrapper(self):
        schema = URLParams([
            optional("birthday", DateTime)
        ])
        d = datetime(year=1991, month=8, day=12)
        self.assertEqual(schema.to_json({"birthday": d}), "birthday=1991-08-12T00%3A00%3A00")
        self.assertEqual(schema.from_json("birthday=1991-08-12T00%3A00%3A00"), {"birthday": d})

    def test_wrong_deep_type(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid Integer"):
            self.schema.from_json('foo=Wha&bars=[1,1.2]')

    def test_unexpected_repeat(self):
        with self.assertRaises(ValidationError):
            self.schema.from_json('foo=Wha&bars=[1]&foo=Bing')


