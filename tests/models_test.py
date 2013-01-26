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
        self.array_normalizer = SchemaSchema().normalize(self.array_schema)
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
        self.object_normalizer = SchemaSchema().normalize(self.object_schema)
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
        self.deep_normalizer = SchemaSchema().normalize(self.deep_schema)

    def test_json(self):
        for i in [1, True, 2.3, "blah", [], {}]:
            self.assertEqual(JSONModel.normalize(i).data, i)

    def test_integer(self):
        self.assertEqual(IntegerSchema().normalize(1), 1)
        self.assertEqual(IntegerSchema().normalize(1.0), 1)
        with self.assertRaisesRegexp(ValidationError, "Invalid integer"):
            IntegerSchema().normalize(1.1)

    def test_float(self):
        self.assertEqual(FloatSchema().normalize(1), 1.0)
        self.assertEqual(FloatSchema().normalize(1.0), 1.0)
        with self.assertRaisesRegexp(ValidationError, "Invalid float"):
            FloatSchema().normalize(True)

    def test_boolean(self):
        self.assertEqual(BooleanSchema().normalize(True), True)
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            BooleanSchema().normalize(0)

    def test_string(self):
        self.assertEqual(StringSchema().normalize("omg"), u"omg")
        self.assertEqual(StringSchema().normalize(u"omg"), u"omg")
        with self.assertRaisesRegexp(ValidationError, "Invalid string"):
            StringSchema().normalize(0)
        with self.assertRaisesRegexp(UnicodeDecodeValidationError, "invalid start byte"):
            StringSchema().normalize("\xff")

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
        self.assertEqual(SchemaSchema().normalize({"type": "integer"}).__class__, IntegerSchema)
        self.assertEqual(SchemaSchema().normalize({"type": "float"}).__class__, FloatSchema)
        self.assertEqual(SchemaSchema().normalize({"type": "boolean"}).__class__, BooleanSchema)
        self.assertEqual(SchemaSchema().normalize({"type": "string"}).__class__, StringSchema)
        self.assertEqual(SchemaSchema().normalize({"type": "core.JSON"}).model_cls, JSONModel)
        self.assertEqual(SchemaSchema().normalize({"type": "core.Schema"}).__class__, SchemaSchema)

    def test_schema_missing_parts(self):
        # Forgot items
        s = self.array_schema.copy()
        s.pop("items")
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            SchemaSchema().normalize(s)
        # Forgot properties
        s = self.object_schema.copy()
        s.pop("properties")
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            SchemaSchema().normalize(s)

    def test_schema_mismatched_parts(self):
        # object with items
        s = self.array_schema.copy()
        s["type"] = "object"
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            SchemaSchema().normalize(s)
        # array with properties
        s = self.object_schema.copy()
        s["type"] = "array"
        with self.assertRaisesRegexp(ValidationError, "Invalid schema"):
            SchemaSchema().normalize(s)

    def test_schema_duplicate_properties(self):
        s = self.object_schema.copy()
        s["properties"][1]["name"] = "foo"
        with self.assertRaisesRegexp(ValidationError, "Duplicate properties"):
            SchemaSchema().normalize(s)

    def test_schema_not_object(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid object"):
            SchemaSchema().normalize(True)

    def test_schema_unknown_type(self):
        with self.assertRaisesRegexp(ValidationError, "Unknown type"):
            SchemaSchema().normalize({"type": "number"})

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
        schema = SchemaSchema().normalize(schema_json)
        self.assertEqual(schema_json, serialize_json(schema))

class TestObjectModel(TestCase):

    def setUp(self):
        class RecipeModel(ObjectModel):
            properties = [
                {
                    "name": "author",
                    "required": True,
                    "schema": {"type": "string"}
                },
                {
                    "name": "spicy",
                    "required": False,
                    "schema": {"type": "boolean"}
                },
                {
                    "name": "meta",
                    "required": False,
                    "schema": {"type": "core.JSON"}
                }
            ]
        self.RecipeModel = RecipeModel
        self.recipe = RecipeModel.normalize({
            "author": "Alex",
            "spicy": True
        })
        self.special_recipe = RecipeModel.normalize({
            "author": "Kyu",
            "meta": {"secret": True}
        })

    def test_normalize_okay(self):
        self.assertEqual(self.recipe.data, {
            u"author": u"Alex",
            u"spicy": True
        })
        self.assertTrue(isinstance(self.special_recipe.data["meta"], JSONModel))

    def test_normalize_fail(self):
        with self.assertRaisesRegexp(ValidationError, "Missing properties"):
            recipe = self.RecipeModel.normalize({
                "maker": "Alex",
                "spicy": True
            })

    def test_getattr(self):
        self.assertEqual(self.recipe.author, "Alex")
        self.assertEqual(self.recipe.spicy, True)
        self.assertEqual(self.recipe.meta, None)
        with self.assertRaises(AttributeError):
            self.recipe.vegetarian

    def test_setattr(self):
        self.recipe.spicy = False
        self.assertEqual(self.recipe.data, {
            u"author": u"Alex",
            u"spicy": False
        })

    def test_setattr_None(self):
        self.recipe.spicy = None
        self.assertEqual(self.recipe.data, {
            u"author": u"Alex"
        })

    def test_serialize(self):
        self.assertEqual(self.special_recipe.serialize(), {
            u"author": u"Kyu",
            u"meta": {u"secret": True}
        })

    def test_get_schema(self):
        self.assertEqual(self.RecipeModel.get_schema(), {
            "type": "object",
            "properties": [
                {
                    "name": "author",
                    "required": True,
                    "schema": {"type": "string"}
                },
                {
                    "name": "spicy",
                    "required": False,
                    "schema": {"type": "boolean"}
                },
                {
                    "name": "meta",
                    "required": False,
                    "schema": {"type": "core.JSON"}
                }
            ]
        })

class TestJSONModel(TestCase):

    def test_repr_simple(self):
        j = JSONModel(True)
        self.assertEqual(repr(j), "<JSONModel true>")
        j = JSONModel({"a":1, "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 8, 7, 6, 5]})
        self.assertEqual(repr(j), '<JSONModel {"a": 1, "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 8, 7, 6, 5]}>')

    def test_repr_truncated(self):
        j = JSONModel({"a":1, "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 8, 7, 6, 5], "c": True, "d": False})
        self.assertEqual(repr(j), '<JSONModel {"a": 1, "c": true, "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 8,  ...>')
