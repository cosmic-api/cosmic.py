from unittest2 import TestCase

from cosmic.exceptions import ValidationError, UnicodeDecodeValidationError
from cosmic.models import *

class TestNormalize(TestCase):

    def setUp(self):
        self.array_schema = {
            "type": "array",
            "items": {
                "type": "boolean"
            }
        }
        self.array_normalizer = SchemaNormalizer().normalize_data(self.array_schema)
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
        self.object_normalizer = SchemaNormalizer().normalize_data(self.object_schema)
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
        self.deep_normalizer = SchemaNormalizer().normalize_data(self.deep_schema)

    def test_json(self):
        for i in [1, True, 2.3, "blah", [], {}]:
            self.assertEqual(JSONData.normalize(i).data, i)

    def test_integer(self):
        self.assertEqual(IntegerNormalizer().normalize_data(1), 1)
        self.assertEqual(IntegerNormalizer().normalize_data(1.0), 1)
        with self.assertRaisesRegexp(ValidationError, "Invalid integer"):
            IntegerNormalizer().normalize_data(1.1)

    def test_float(self):
        self.assertEqual(FloatNormalizer().normalize_data(1), 1.0)
        self.assertEqual(FloatNormalizer().normalize_data(1.0), 1.0)
        with self.assertRaisesRegexp(ValidationError, "Invalid float"):
            FloatNormalizer().normalize_data(True)

    def test_boolean(self):
        self.assertEqual(BooleanNormalizer().normalize_data(True), True)
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            BooleanNormalizer().normalize_data(0)

    def test_string(self):
        self.assertEqual(StringNormalizer().normalize_data("omg"), u"omg")
        self.assertEqual(StringNormalizer().normalize_data(u"omg"), u"omg")
        with self.assertRaisesRegexp(ValidationError, "Invalid string"):
            StringNormalizer().normalize_data(0)
        with self.assertRaisesRegexp(UnicodeDecodeValidationError, "invalid start byte"):
            StringNormalizer().normalize_data("\xff")

    def test_binary(self):
        self.assertEqual(BinaryNormalizer().normalize_data('YWJj'), "abc")
        self.assertEqual(BinaryNormalizer().normalize_data(u'YWJj'), "abc")
        with self.assertRaisesRegexp(ValidationError, "Invalid base64"):
            # Will complain about incorrect padding
            BinaryNormalizer().normalize_data("a")
        with self.assertRaisesRegexp(ValidationError, "Invalid binary"):
            BinaryNormalizer().normalize_data(1)

    def test_array(self):
        self.assertEqual(self.array_normalizer.normalize_data([True, False]), [True, False])
        with self.assertRaisesRegexp(ValidationError, "Invalid array"):
            self.array_normalizer.normalize_data(("no", "tuples",))
        with self.assertRaisesRegexp(ValidationError, "Invalid boolean"):
            self.array_normalizer.normalize_data([True, False, 1])

    def test_object(self):
        res = self.object_normalizer.normalize_data({"foo": True, "bar": 2.0})
        self.assertEqual(res, {"foo": True, "bar": 2})
        with self.assertRaisesRegexp(ValidationError, "Invalid object"):
            self.object_normalizer.normalize_data([])
        # Problems with properties
        with self.assertRaisesRegexp(ValidationError, "Missing properties"):
            self.object_normalizer.normalize_data({"bar": 2.0})
        with self.assertRaisesRegexp(ValidationError, "Unexpected properties"):
            self.object_normalizer.normalize_data({"foo": True, "barr": 2.0})

    def test_schema(self):
        self.assertTrue(isinstance(Schema.normalize({"type": "integer"}), IntegerNormalizer))
        self.assertTrue(isinstance(Schema.normalize({"type": "float"}), FloatNormalizer))
        self.assertTrue(isinstance(Schema.normalize({"type": "boolean"}), BooleanNormalizer))
        self.assertTrue(isinstance(Schema.normalize({"type": "string"}), StringNormalizer))
        self.assertTrue(isinstance(Schema.normalize({"type": "binary"}), BinaryNormalizer))
        self.assertTrue(isinstance(Schema.normalize({"type": "json"}), JSONDataNormalizer))
        self.assertTrue(isinstance(Schema.normalize({"type": "schema"}), SchemaNormalizer))

    def test_schema_missing_parts(self):
        # Forgot items
        s = self.array_schema.copy()
        s.pop("items")
        with self.assertRaisesRegexp(ValidationError, "Missing properties"):
            SchemaNormalizer().normalize_data(s)
        # Forgot properties
        s = self.object_schema.copy()
        s.pop("properties")
        with self.assertRaisesRegexp(ValidationError, "Missing properties"):
            SchemaNormalizer().normalize_data(s)

    def test_schema_extra_parts(self):
        # object with items
        s = self.array_schema.copy()
        s["properties"] = self.object_schema["properties"]
        with self.assertRaisesRegexp(ValidationError, "Unexpected properties"):
            SchemaNormalizer().normalize_data(s)
        # array with properties
        s = self.object_schema.copy()
        s["items"] = self.array_schema["items"]
        with self.assertRaisesRegexp(ValidationError, "Unexpected properties"):
            SchemaNormalizer().normalize_data(s)

    def test_schema_duplicate_properties(self):
        s = self.object_schema.copy()
        s["properties"][1]["name"] = "foo"
        with self.assertRaisesRegexp(ValidationError, "Duplicate properties"):
            SchemaNormalizer().normalize_data(s)

    def test_schema_not_object(self):
        with self.assertRaisesRegexp(ValidationError, "Invalid schema: True"):
            SchemaNormalizer().normalize_data(True)

    def test_schema_unknown_type(self):
        with self.assertRaisesRegexp(ValidationError, "Unknown type"):
            SchemaNormalizer().normalize_data({"type": "number"})

    def test_deep_schema_validation_stack(self):
        with self.assertRaisesRegexp(ValidationError, "[0]"):
            self.deep_normalizer.normalize_data([{"foo": True, "bar": False}])

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
        schema = SchemaNormalizer().normalize_data(schema_json)
        self.assertEqual(schema_json, schema.serialize())

    def serialize_binary(self):
        self.assertEqual(BinaryNormalizer().serialize_data("abc"), 'YWJj')

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
                    "schema": {"type": "json"}
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
        self.assertTrue(isinstance(self.special_recipe.data["meta"], JSONData))

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

    def test_setattr_None_then_serialize(self):
        self.recipe.spicy = None
        self.assertEqual(self.recipe.serialize(), {
            u"author": u"Alex"
        })

    def test_serialize_okay(self):
        self.assertEqual(self.special_recipe.serialize(), {
            u"author": u"Kyu",
            u"meta": {u"secret": True}
        })

    def test_get_schema(self):
        self.assertEqual(self.RecipeModel.get_schema().serialize(), {
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
                    "schema": {"type": "json"}
                }
            ]
        })

class TestJSONData(TestCase):

    def test_repr_simple(self):
        j = JSONData(True)
        self.assertEqual(repr(j), "<JSONData true>")
        j = JSONData({"a":1, "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 8, 7, 6, 5]})
        self.assertEqual(repr(j), '<JSONData {"a": 1, "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 8, 7, 6, 5]}>')

    def test_repr_truncated(self):
        j = JSONData({"a":1, "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 8, 7, 6, 5], "c": True, "d": False})
        self.assertEqual(repr(j), '<JSONData {"a": 1, "c": true, "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 8,  ...>')
