from unittest2 import TestCase

from apio.exceptions import ValidationError, UnicodeDecodeValidationError
from apio.models import *

class TestNormalize(TestCase):

    def setUp(self):
        self.array_schema = {
            "type": "array",
            "items": {
                "type": "boolean"
            }
        }
        self.array_normalizer = normalize_schema(self.array_schema)
        self.object_schema = {
            "type": "object",
            "properties": [
                {
                    "name": "foo",
                    "required": True,
                    "schema": {"type": "boolean"}
                },
                {
                    "name": "bar",
                    "required": False,
                    "schema": {"type": "integer"}
                }
            ]
        }
        self.object_normalizer = normalize_schema(self.object_schema)

    def test_any(self):
        for i in [1, True, 2.3, "blah", [], {}]:
            self.assertEqual(normalize_wildcard(i), i)

    def test_integer(self):
        self.assertEqual(normalize_integer(1), 1)
        self.assertEqual(normalize_integer(1.0), 1)
        with self.assertRaisesRegexp(ValidationError, "Invalid integer"):
            normalize_integer(1.1)

    def test_float(self):
        self.assertEqual(normalize_float(1), 1.0)
        self.assertEqual(normalize_float(1.0), 1.0)
        with self.assertRaisesRegexp(ValidationError, "Invalid float"):
            normalize_float(True)

    def test_boolean(self):
        self.assertEqual(normalize_boolean(True), True)
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            normalize_boolean(0)

    def test_string(self):
        self.assertEqual(normalize_string("omg"), u"omg")
        self.assertEqual(normalize_string(u"omg"), u"omg")
        with self.assertRaisesRegexp(ValidationError, "Invalid string"):
            normalize_string(0)
        with self.assertRaisesRegexp(UnicodeDecodeValidationError, "invalid start byte"):
            normalize_string("\xff")

    def test_array(self):
        self.assertEqual(self.array_normalizer([True, False]), [True, False])
        with self.assertRaisesRegexp(ValidationError, "Invalid array"):
            self.array_normalizer(("no", "tuples",))
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            self.array_normalizer([True, False, 1])

    def test_object(self):
        res = self.object_normalizer({"foo": True, "bar": 2.0})
        self.assertEqual(res, {"foo": True, "bar": 2})
        with self.assertRaisesRegexp(ValidationError, "Invalid object"):
            self.object_normalizer([])
        # Problems with properties
        with self.assertRaisesRegexp(ValidationError, "Missing properties"):
            self.object_normalizer({"bar": 2.0})
        with self.assertRaisesRegexp(ValidationError, "Unexpected properties"):
            self.object_normalizer({"foo": True, "barr": 2.0})

    def test_schema(self):
        self.assertEqual(normalize_schema({"type": "integer"}), normalize_integer)
        self.assertEqual(normalize_schema({"type": "float"}), normalize_float)
        self.assertEqual(normalize_schema({"type": "boolean"}), normalize_boolean)
        self.assertEqual(normalize_schema({"type": "string"}), normalize_string)
        self.assertEqual(normalize_schema({"type": "any"}), normalize_wildcard)
        self.assertEqual(normalize_schema({"type": "schema"}), normalize_schema)

    def test_schema_missing_parts(self):
        # Forgot items
        s = self.array_schema.copy()
        s.pop("items")
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            normalize_schema(s)
        # Forgot properties
        s = self.object_schema.copy()
        s.pop("properties")
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            normalize_schema(s)

    def test_schema_mismatched_parts(self):
        # object with items
        s = self.array_schema.copy()
        s["type"] = "object"
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            normalize_schema(s)
        # array with properties
        s = self.object_schema.copy()
        s["type"] = "array"
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            normalize_schema(s)

    def test_schema_duplicate_properties(self):
        s = self.object_schema.copy()
        s["properties"][1]["name"] = "foo"
        with self.assertRaisesRegexp(ValidationError, "Duplicate properties"):
            normalize_schema(s)

    def test_schema_not_object(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid object"):
            normalize_schema(True)

    def test_schema_unknown_type(self):
        with self.assertRaisesRegexp(ValidationError, "Unknown type"):
            normalize_schema({"type": "number"})

