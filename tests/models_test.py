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
        self.array_normalizer = SchemaSchema.normalize(self.array_schema)
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
        self.object_normalizer = SchemaSchema.normalize(self.object_schema)
        self.deep_schema = {
            "type": "array",
            "items": {
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
        }
        self.deep_normalizer = SchemaSchema.normalize(self.deep_schema)

    def test_any(self):
        for i in [1, True, 2.3, "blah", [], {}]:
            self.assertEqual(JSONSchema.normalize(i).data, i)

    def test_integer(self):
        self.assertEqual(IntegerSchema.normalize(1), 1)
        self.assertEqual(IntegerSchema.normalize(1.0), 1)
        with self.assertRaisesRegexp(ValidationError, "Invalid integer"):
            IntegerSchema.normalize(1.1)

    def test_float(self):
        self.assertEqual(FloatSchema.normalize(1), 1.0)
        self.assertEqual(FloatSchema.normalize(1.0), 1.0)
        with self.assertRaisesRegexp(ValidationError, "Invalid float"):
            FloatSchema.normalize(True)

    def test_boolean(self):
        self.assertEqual(BooleanSchema.normalize(True), True)
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            BooleanSchema.normalize(0)

    def test_string(self):
        self.assertEqual(StringSchema.normalize("omg"), u"omg")
        self.assertEqual(StringSchema.normalize(u"omg"), u"omg")
        with self.assertRaisesRegexp(ValidationError, "Invalid string"):
            StringSchema.normalize(0)
        with self.assertRaisesRegexp(UnicodeDecodeValidationError, "invalid start byte"):
            StringSchema.normalize("\xff")

    def test_array(self):
        self.assertEqual(self.array_normalizer.normalize([True, False]), [True, False])
        with self.assertRaisesRegexp(ValidationError, "Invalid array"):
            self.array_normalizer.normalize(("no", "tuples",))
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            self.array_normalizer.normalize([True, False, 1])

    def test_object(self):
        res = self.object_normalizer.normalize({"foo": True, "bar": 2.0})
        self.assertEqual(res, {"foo": True, "bar": 2})
        with self.assertRaisesRegexp(ValidationError, "Invalid object"):
            self.object_normalizer.normalize([])
        # Problems with properties
        with self.assertRaisesRegexp(ValidationError, "Missing properties"):
            self.object_normalizer.normalize({"bar": 2.0})
        with self.assertRaisesRegexp(ValidationError, "Unexpected properties"):
            self.object_normalizer.normalize({"foo": True, "barr": 2.0})

    def test_schema(self):
        self.assertEqual(SchemaSchema.normalize({"type": "integer"}), IntegerSchema)
        self.assertEqual(SchemaSchema.normalize({"type": "float"}), FloatSchema)
        self.assertEqual(SchemaSchema.normalize({"type": "boolean"}), BooleanSchema)
        self.assertEqual(SchemaSchema.normalize({"type": "string"}), StringSchema)
        self.assertEqual(SchemaSchema.normalize({"type": "any"}), JSONSchema)
        self.assertEqual(SchemaSchema.normalize({"type": "schema"}), SchemaSchema)

    def test_schema_missing_parts(self):
        # Forgot items
        s = self.array_schema.copy()
        s.pop("items")
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            SchemaSchema.normalize(s)
        # Forgot properties
        s = self.object_schema.copy()
        s.pop("properties")
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            SchemaSchema.normalize(s)

    def test_schema_mismatched_parts(self):
        # object with items
        s = self.array_schema.copy()
        s["type"] = "object"
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            SchemaSchema.normalize(s)
        # array with properties
        s = self.object_schema.copy()
        s["type"] = "array"
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            SchemaSchema.normalize(s)

    def test_schema_duplicate_properties(self):
        s = self.object_schema.copy()
        s["properties"][1]["name"] = "foo"
        with self.assertRaisesRegexp(ValidationError, "Duplicate properties"):
            SchemaSchema.normalize(s)

    def test_schema_not_object(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid object"):
            SchemaSchema.normalize(True)

    def test_schema_unknown_type(self):
        with self.assertRaisesRegexp(ValidationError, "Unknown type"):
            SchemaSchema.normalize({"type": "number"})

    def test_deep_schema_validation_stack(self):
        with self.assertRaisesRegexp(ValidationError, "[0]"):
            self.deep_normalizer.normalize([{"foo": True, "bar": False}])

class TestSerialize(TestCase):

    def test_serialize_schema(self):
        self.maxDiff = None
        schema_json = {
            u"type": u"array",
            u"items": {
                u"type": u"object",
                u"properties": [
                    {
                        u"name": u"foo",
                        u"required": True,
                        u"schema": {u"type": u"boolean"}
                    },
                    {
                        u"name": u"bar",
                        u"required": False,
                        u"schema": {u"type": u"integer"}
                    }
                ]
            }
        }
        schema = SchemaSchema.normalize(schema_json)
        self.assertEqual(schema_json, serialize_json(schema))
