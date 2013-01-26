from unittest2 import TestCase
from mock import patch, Mock

from apio.exceptions import *
from apio.tools import *
from apio.models import *

class TestGetArgSpec(TestCase):

    def test_no_args(self):
        def f(): pass
        self.assertEqual(get_arg_spec(f), None)

    def test_one_arg(self):
        def f(x): pass
        self.assertEqual(get_arg_spec(f).serialize(), {
            'type': 'core.JSON'
        })
        def f(x=1): pass
        self.assertEqual(get_arg_spec(f).serialize(), {
            'type': 'core.JSON'
        })

    def test_multiple_args(self):
        def f(x, y): pass
        self.assertEqual(get_arg_spec(f).serialize(), {
            'type': 'object',
            'properties': [
                {
                    "name": "x",
                    "required": True,
                    "schema": {"type": "core.JSON"}
                },
                {
                    "name": "y",
                    "required": True,
                    "schema": {"type": "core.JSON"}
                }
            ]
        })

    def test_multiple_args_and_kwargs(self):
        def f(x, y=1): pass
        self.assertEqual(get_arg_spec(f).serialize(), {
            'type': 'object',
            'properties': [
                {
                    "name": "x",
                    "required": True,
                    "schema": {"type": "core.JSON"}
                },
                {
                    "name": "y",
                    "required": False,
                    "schema": {"type": "core.JSON"}
                }
            ]
        })

    def test_multiple_kwargs(self):
        def f(x=0, y=1): pass
        self.assertEqual(get_arg_spec(f).serialize(), {
            'type': 'object',
            'properties': [
                {
                    "name": "x",
                    "required": False,
                    "schema": {"type": "core.JSON"}
                },
                {
                    "name": "y",
                    "required": False,
                    "schema": {"type": "core.JSON"}
                }
            ]
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
            apply_to_action_func(f, JSONModel("oops"))

    def test_one_arg_okay(self):
        def f(a): return a
        self.assertEqual(apply_to_action_func(f, JSONModel(1)), 1)

    def test_one_arg_fail(self):
        with self.assertRaises(SpecError):
            def f(a): return a
            apply_to_action_func(f, None)

    def test_one_kwarg_okay(self):
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, JSONModel(1)), 1)
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, JSONModel({})), {})
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, None), 2)

    def test_one_kwarg_passed_none(self):
        # None is an explicit value
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, JSONModel(None)), None)

    def test_multiple_args_and_kwargs_okay(self):
        def f(a, b=1): return a, b
        res = apply_to_action_func(f, JSONModel({'a': 2}))
        self.assertEqual(res, (2, 1,))
        def f(a, b=1): return a, b
        res = apply_to_action_func(f, JSONModel({'a': 2, 'b': 2}))
        self.assertEqual(res, (2, 2,))

    def test_multiple_kwargs_okay(self):
        def f(a=5, b=1): return a, b
        self.assertEqual(apply_to_action_func(f, JSONModel({})), (5, 1,))

    def test_unknown_kwarg(self):
        with self.assertRaises(SpecError):
            def f(a=5, b=1): return a, b
            apply_to_action_func(f, JSONModel({'c': 4}))

    def test_not_an_object(self):
        with self.assertRaises(SpecError):
            def f(a=5, b=1): return a, b
            apply_to_action_func(f, JSONModel("hello"))

    def test_missing_required_arg(self):
        with self.assertRaises(SpecError):
            def f(a, b=1): return a, b
            apply_to_action_func(f, JSONModel({}))

class TestSerializeActionArguments(TestCase):

    def test_one_arg(self):
        res = serialize_action_arguments("universe").data
        self.assertEqual(res, "universe")

    def test_one_kwarg(self):
        res = serialize_action_arguments(what="universe").data
        self.assertEqual(res, {"what": "universe"})

    def test_many_kwargs(self):
        ser = serialize_action_arguments(what="universe", when="now")
        self.assertEqual(ser.data, {"what": "universe", "when": "now"})

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
        json_schema = SchemaModel(ModelNormalizer(JSONModel))
        assert schema_is_compatible(json_schema, SchemaModel(IntegerNormalizer()))
        assert schema_is_compatible(json_schema, SchemaModel(FloatNormalizer()))

    def test_object_keys_mismatch(self):
        g = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            },
            {
                u"name": u"b",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        d = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            },
            {
                u"name": u"c",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        assert not schema_is_compatible(g, d)
    def test_object_keys_mismatch(self):
        g = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            },
            {
                u"name": u"b",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        d = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            },
            {
                u"name": u"c",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        assert not schema_is_compatible(g, d)

    def test_object_number_mismatch(self):
        g = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        d = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            },
            {
                u"name": u"b",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        assert not schema_is_compatible(g, d)

    def test_object_match(self):
        g = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": True,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        d = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": True,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        assert schema_is_compatible(g, d)

    def test_object_no_match(self):
        g = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": True,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        d = SchemaModel(ObjectNormalizer([
            {
                u"name": u"a",
                u"required": False,
                u"schema": SchemaModel(IntegerNormalizer())
            }
        ]))
        assert not schema_is_compatible(g, d)


class TestNamespace(TestCase):

    def setUp(self):
        self.dispatcher = Namespace()
        length = Mock(return_value=3)
        length.spec = { 'name': 'length' }
        self.dispatcher.add('length', length)
        height = Mock()
        height.spec = { 'name': 'height' }
        self.dispatcher.add('height', height)

    def test_call(self):
        self.assertEqual(self.dispatcher.length([0, 1, 2]), 3)

    def test_iterate(self):
        l = [action for action in self.dispatcher]
        self.assertEqual(l[0].spec['name'], 'length')
        self.assertEqual(l[1].spec['name'], 'height')

    def test_all(self):
        self.assertEqual(self.dispatcher.__all__, ['length', 'height'])

    def test_undefined_action(self):
        with self.assertRaisesRegexp(SpecError, "not defined"):
            self.dispatcher.width([0, 1, 2])

