from unittest2 import TestCase

from apio.exceptions import *
from apio.tools import *

class TestGetArgSpec(TestCase):

    def test_no_args(self):
        def f(): pass
        self.assertEqual(get_arg_spec(f), None)

    def test_one_arg(self):
        def f(x): pass
        self.assertEqual(get_arg_spec(f), {
            'type': 'any'
        })
        def f(x=1): pass
        self.assertEqual(get_arg_spec(f), {
            'type': 'any'
        })

    def test_multiple_args(self):
        def f(x, y): pass
        self.assertEqual(get_arg_spec(f), {
            'type': 'object',
            'properties': {
                'x': {
                    'type': 'any',
                    'required': True
                },
                'y': {
                    'type': 'any',
                    'required': True
                }
            }
        })

    def test_multiple_args_and_kwargs(self):
        def f(x, y=1): pass
        self.assertEqual(get_arg_spec(f), {
            'type': 'object',
            'properties': {
                'x': {
                    'type': 'any',
                    'required': True
                },
                'y': {
                    'type': 'any'
                }
            }
        })

    def test_multiple_kwargs(self):
        def f(x=0, y=1): pass
        self.assertEqual(get_arg_spec(f), {
            'type': 'object',
            'properties': {
                'x': {
                    'type': 'any'
                },
                'y': {
                    'type': 'any'
                }
            }
        })

    def test_splats(self):
        def f(x=0, *args): pass
        with self.assertRaises(SpecError):
            get_arg_spec(f)
        def f(*args, **kwargs): pass
        with self.assertRaises(SpecError):
            get_arg_spec(f)
        def f(x, y, z=1, **kwargs): pass
        with self.assertRaises(SpecError):
            get_arg_spec(f)

class TestApplyToActionFunc(TestCase):

    def test_no_arg_okay(self):
        def f(): return "okay"
        self.assertEqual(apply_to_action_func(f, None), "okay")

    def test_no_arg_fail(self):
        def f(): return "okay"
        with self.assertRaises(SpecError):
            apply_to_action_func(f, JSONPayload("oops"))

    def test_one_arg_okay(self):
        def f(a): return a
        self.assertEqual(apply_to_action_func(f, JSONPayload(1)), 1)

    def test_one_arg_fail(self):
        with self.assertRaises(SpecError):
            def f(a): return a
            apply_to_action_func(f, None)

    def test_one_kwarg_okay(self):
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, JSONPayload(1)), 1)
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, JSONPayload({})), {})
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, None), 2)

    def test_one_kwarg_passed_none(self):
        # None is an explicit value
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, JSONPayload(None)), None)

    def test_multiple_args_and_kwargs_okay(self):
        def f(a, b=1): return a, b
        res = apply_to_action_func(f, JSONPayload({'a': 2}))
        self.assertEqual(res, (2, 1,))
        def f(a, b=1): return a, b
        res = apply_to_action_func(f, JSONPayload({'a': 2, 'b': 2}))
        self.assertEqual(res, (2, 2,))

    def test_multiple_kwargs_okay(self):
        def f(a=5, b=1): return a, b
        self.assertEqual(apply_to_action_func(f, JSONPayload({})), (5, 1,))

    def test_unknown_kwarg(self):
        with self.assertRaises(SpecError):
            def f(a=5, b=1): return a, b
            apply_to_action_func(f, JSONPayload({'c': 4}))

    def test_not_an_object(self):
        with self.assertRaises(SpecError):
            def f(a=5, b=1): return a, b
            apply_to_action_func(f, JSONPayload("hello"))

    def test_missing_required_arg(self):
        with self.assertRaises(SpecError):
            def f(a, b=1): return a, b
            apply_to_action_func(f, JSONPayload({}))

class TestSerializeActionArguments(TestCase):

    def test_one_arg(self):
        res = serialize_action_arguments("universe").json
        self.assertEqual(res, "universe")

    def test_one_kwarg(self):
        res = serialize_action_arguments(what="universe").json
        self.assertEqual(res, {"what": "universe"})

    def test_many_kwargs(self):
        ser = serialize_action_arguments(what="universe", when="now")
        self.assertEqual(ser.json, {"what": "universe", "when": "now"})

    def test_multiple_args(self):
        with self.assertRaises(SpecError):
            serialize_action_arguments("universe", "now")

    def test_no_args_no_kwargs(self):
        self.assertEqual(serialize_action_arguments(), None)

    def test_mixed_args_and_kwargs(self):
        with self.assertRaises(SpecError):
            serialize_action_arguments("universe", when="now")

class TestSchemaIsCompatible(TestCase):

    def test_base_cases(self):
        assert schema_is_compatible({"type": "any"}, {"type": "object"})
        assert schema_is_compatible({"type": "any"}, {"type": "array"})

    def test_object_keys_mismatch(self):
        g = {
            "type": "object",
            "properties": {
                "a": { "type": "any" },
                "b": { "type": "any" }
            }
        }
        d = {
            "type": "object",
            "properties": {
                "a": { "type": "any" },
                "c": { "type": "any" }
            }
        }
        assert not schema_is_compatible(g, d)

    def test_object_match(self):
        g = {
            "type": "object",
            "properties": {
                "a": { "type": "any" },
                "b": { "type": "any", "required": True }
            }
        }
        d = {
            "type": "object",
            "properties": {
                "a": { "type": "boolean", "required": False },
                "b": { "type": "boolean", "required": True }
            }
        }
        assert schema_is_compatible(g, d)

    def test_object_no_match(self):
        g = {
            "type": "object",
            "properties": {
                "a": { "type": "any" },
                "b": { "type": "any", "required": True }
            }
        }
        d = {
            "type": "object",
            "properties": {
                "a": { "type": "boolean" },
                "b": { "type": "boolean" }
            }
        }
        assert not schema_is_compatible(g, d)

class TestNormalize(TestCase):

    def setUp(self):
        self.array_schema = {
            "type": "array",
            "items": {
                "type": "bool"
            }
        }
        self.object_schema = {
            "type": "object",
            "properties": [
                {
                    "name": "foo",
                    "required": True,
                    "schema": {
                        "type": "bool"
                    }
                },
                {
                    "name": "bar",
                    "required": False,
                    "schema": {
                        "type": "int"
                    }
                }
            ]
        }

    def test_base_cases_okay(self):
        self.assertEqual(normalize({"type": "any"}, 1), 1)
        self.assertEqual(normalize({"type": "int"}, 1), 1)
        self.assertEqual(normalize({"type": "bool"}, True), True)
        self.assertEqual(normalize({"type": "string"}, u"omg"), u"omg")
        self.assertEqual(normalize({"type": "float"}, 1.0), 1.0)

    def test_float_for_int(self):
        self.assertEqual(normalize({"type": "int"}, 2.0), 2)

    def test_cast_int_to_float(self):
        self.assertEqual(normalize({"type": "float"}, 1), 1.0)

    def test_base_case_errors(self):
        with self.assertRaisesRegexp(ValidationError, "Expected bool"):
            normalize({"type": "bool"}, 1)
        with self.assertRaisesRegexp(ValidationError, "unicode string"):
            normalize({"type": "string"}, "not unicode")

    def test_array_recurse_okay(self):
        res = normalize(self.array_schema, [True, False])
        self.assertEqual(res, [True, False])

    def test_array_recurse_fail(self):
        with self.assertRaisesRegexp(ValidationError, "Expected bool"):
            normalize(self.array_schema, [True, False, 1])

    def test_object_recurse_okay(self):
        res = normalize(self.object_schema, {"foo": True, "bar": 2.0})
        self.assertEqual(res, {"foo": True, "bar": 2})

    def test_object_recurse_missing(self):
        with self.assertRaisesRegexp(ValidationError, "Missing properties"):
            normalize(self.object_schema, {"bar": 2.0})

    def test_object_recurse_unexpected(self):
        with self.assertRaisesRegexp(ValidationError, "Unexpected properties"):
            normalize(self.object_schema, {"foo": True, "barr": 2.0})
