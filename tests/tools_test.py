from unittest2 import TestCase
from mock import patch, Mock

from cosmic.exceptions import *
from cosmic.tools import *
from cosmic import cosmos

from teleport import Integer, Float, Struct, required, optional, Box, Schema

class TestGetArgSpec(TestCase):

    def test_no_args(self):
        def f(): pass
        self.assertEqual(get_arg_spec(f), None)

    def test_one_arg(self):
        def f(x): pass
        self.assertEqual(Schema().serialize(get_arg_spec(f)), {
            'type': 'json'
        })
        def f(x=1): pass
        self.assertEqual(Schema().serialize(get_arg_spec(f)), {
            'type': 'json'
        })

    def test_multiple_args(self):
        def f(x, y): pass
        self.assertEqual(Schema().serialize(get_arg_spec(f)), {
            'type': "struct",
            "fields": [
                {
                    "name": "x",
                    "required": True,
                    "schema": {"type": "json"}
                },
                {
                    "name": "y",
                    "required": True,
                    "schema": {"type": "json"}
                }
            ]
        })

    def test_multiple_args_and_kwargs(self):
        def f(x, y=1): pass
        self.assertEqual(Schema().serialize(get_arg_spec(f)), {
            'type': u"struct",
            "fields": [
                {
                    "name": u"x",
                    "required": True,
                    "schema": {"type": u"json"}
                },
                {
                    "name": u"y",
                    "required": False,
                    "schema": {"type": u"json"}
                }
            ]
        })

    def test_multiple_kwargs(self):
        def f(x=0, y=1): pass
        self.assertEqual(Schema().serialize(get_arg_spec(f)), {
            'type': u"struct",
            "fields": [
                {
                    "name": u"x",
                    "required": False,
                    "schema": {"type": u"json"}
                },
                {
                    "name": u"y",
                    "required": False,
                    "schema": {"type": u"json"}
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

class TestApplyToFunc(TestCase):

    def test_no_arg_okay(self):
        def f(): return "okay"
        self.assertEqual(apply_to_func(f, None), "okay")

    def test_one_arg_okay(self):
        def f(a): return a
        self.assertEqual(apply_to_func(f, 1), 1)

    def test_one_kwarg_okay(self):
        def f(a=2): return a
        self.assertEqual(apply_to_func(f, 1), 1)
        self.assertEqual(apply_to_func(f, {}), {})
        self.assertEqual(apply_to_func(f, None), 2)

    def test_one_kwarg_passed_none(self):
        # None is an explicit value
        def f(a=2): return a
        n = Box(None)
        self.assertEqual(apply_to_func(f, n), n)

    def test_multiple_args_and_kwargs_okay(self):
        def f(a, b=1): return a, b
        res = apply_to_func(f, {'a': 2})
        self.assertEqual(res, (2, 1,))
        res = apply_to_func(f, {'a': 2, 'b': 2})
        self.assertEqual(res, (2, 2,))

    def test_multiple_kwargs_okay(self):
        def f(a=5, b=1): return a, b
        self.assertEqual(apply_to_func(f, {}), (5, 1,))


class TestPackActionArguments(TestCase):

    def test_one_arg(self):
        res = pack_action_arguments("universe")
        self.assertEqual(res, "universe")

    def test_one_kwarg(self):
        res = pack_action_arguments(what="universe")
        self.assertEqual(res, {"what": "universe"})

    def test_many_kwargs(self):
        res = pack_action_arguments(what="universe", when="now")
        self.assertEqual(res, {"what": "universe", "when": "now"})

    def test_multiple_args(self):
        with self.assertRaises(SpecError):
            pack_action_arguments("universe", "now")

    def test_no_args_no_kwargs(self):
        self.assertEqual(pack_action_arguments(), None)

    def test_mixed_args_and_kwargs(self):
        with self.assertRaises(SpecError):
            pack_action_arguments("universe", when="now")

class TestSchemaIsCompatible(TestCase):

    def test_base_cases(self):
        json_schema = JSON()
        assert schema_is_compatible(json_schema, Integer())
        assert schema_is_compatible(json_schema, Float())

    def test_object_keys_mismatch(self):
        g = Struct([
            optional("a", Integer()),
            optional("b", Integer())
        ])
        d = Struct([
            optional("a", Integer()),
            optional("c", Integer())
        ])
        assert not schema_is_compatible(g, d)

    def test_object_number_mismatch(self):
        g = Struct([
            optional("a", Integer())
        ])
        d = Struct([
            optional("a", Integer()),
            optional("b", Integer())
        ])
        assert not schema_is_compatible(g, d)

    def test_object_match(self):
        g = Struct([
            required("a", Integer())
        ])
        d = Struct([
            required("a", Integer())
        ])
        assert schema_is_compatible(g, d)

    def test_object_no_match(self):
        g = Struct([
            required("a", Integer())
        ])
        d = Struct([
            optional("a", Integer())
        ])
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
        with self.assertRaises(KeyError):
            self.dispatcher.width([0, 1, 2])


class TestSchemaHelpers(TestCase):

    def setUp(self):
        self.api = {
            "name": u"Foo",
            "actions": [
                {
                    "name": u"foo",
                    "accepts": {"type": u"string"},
                    "returns": {"type": u"boolean"}
                }
            ],
            "models": []
        }

    def test_deserialize_schema(self):
        with cosmos:
            schema = Schema().deserialize({"type": "cosmic.API"})
            self.assertEqual(schema.deserialize(self.api).__class__.__name__, "API")

    def test_normalize_json(self):
        with self.assertRaisesRegexp(ValidationError, "Expected Box, found None"):
            normalize_json(Integer(), None)
        with self.assertRaisesRegexp(ValidationError, "Expected None, found Box"):
            normalize_json(None, Box(1))
        self.assertEqual(normalize_json(None, None), None)
        self.assertEqual(normalize_json(Integer(), Box(1)), 1)

    def test_serialize_json(self):
        with self.assertRaisesRegexp(ValidationError, "Expected data, found None"):
            serialize_json(Integer(), None)
        with self.assertRaisesRegexp(ValidationError, "Expected None, found data"):
            serialize_json(None, 1)
        self.assertEqual(serialize_json(None, None), None)
        self.assertEqual(serialize_json(Integer(), 1).datum, 1)

    def test_string_to_json(self):
        self.assertEqual(string_to_json(""), None)
        self.assertEqual(string_to_json("1").datum, 1)

    def test_json_to_string(self):
        self.assertEqual(json_to_string(None), "")
        self.assertEqual(json_to_string(Box(1)), "1")
