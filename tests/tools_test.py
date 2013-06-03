from unittest2 import TestCase
from mock import patch, Mock

from cosmic.exceptions import *
from cosmic.tools import *
from cosmic import cosmos

from teleport import *


class TestGetArgs(TestCase):

    def test_try_splats(self):
        def f(*arg): pass
        with self.assertRaisesRegexp(SpecError, "splats"):
            get_args(f)

    def test_no_args(self):
        def f(): pass
        self.assertEqual(get_args(f), ((), (),))

    def test_one_arg(self):
        def f(x): pass
        self.assertEqual(get_args(f), (("x",), (),))
        def f(x=1): pass
        self.assertEqual(get_args(f), ((), ("x",),))

    def test_multiple_args(self):
        def f(x, y): pass
        self.assertEqual(get_args(f), (("x", "y",), (),))

    def test_multiple_args_and_kwargs(self):
        def f(x, y=1): pass
        self.assertEqual(get_args(f), (("x",), ("y",),))

    def test_multiple_kwargs(self):
        def f(x=0, y=1): pass
        self.assertEqual(get_args(f), ((), ("x", "y",),))



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


class TestAssertIsCompatible(TestCase):

    def test_base_cases(self):
        with self.assertRaisesRegexp(SpecError, "needs to accept"):
            assert_is_compatible(JSON, (), ())
        assert_is_compatible(JSON, ("a",), ())
        assert_is_compatible(JSON, (), ("a",))

    def test_not_struct(self):
        with self.assertRaisesRegexp(SpecError, "be a Struct"):
            assert_is_compatible(JSON, ("a", "b",), ())

    def test_missing_required_field(self):
        s = Struct([
            required("a", Integer),
        ])
        with self.assertRaisesRegexp(SpecError, "required field"):
            assert_is_compatible(s, ("a", "b",), ())

    def test_field_should_be_required(self):
        s = Struct([
            required("a", Integer),
            optional("b", Integer)
        ])
        with self.assertRaisesRegexp(SpecError, "required field"):
            assert_is_compatible(s, ("a", "b",), ())

    def test_missing_function_argument(self):
        s = Struct([
            required("a", Integer),
            required("b", Integer),
            optional("c", Integer)
        ])
        with self.assertRaisesRegexp(SpecError, "function argument"):
            assert_is_compatible(s, ("a","b",), ())
        with self.assertRaisesRegexp(SpecError, "function argument"):
            assert_is_compatible(s, ("a",), ("b",))


class TestGetterNamespace(TestCase):

    def setUp(self):
        self.d = OrderedDict([('a', 1,), ('b', 2,), ('c', 3,)])
        self.dispatcher = GetterNamespace(
            get_item=self.d.__getitem__,
            get_all=self.d.keys)

    def test_get_item(self):
        self.assertEqual(self.dispatcher.a, 1)
        self.assertEqual(self.dispatcher.b, 2)
        self.assertEqual(self.dispatcher.c, 3)
        with self.assertRaises(KeyError):
            self.dispatcher.d

    def test_all(self):
        self.assertEqual(self.dispatcher.__all__, ['a', 'b', 'c'])


class TestSchemaHelpers(TestCase):

    def test_deserialize_json(self):
        with self.assertRaisesRegexp(ValidationError, "Expected Box, found None"):
            deserialize_json(Integer, None)
        with self.assertRaisesRegexp(ValidationError, "Expected None, found Box"):
            deserialize_json(None, Box(1))
        self.assertEqual(deserialize_json(None, None), None)
        self.assertEqual(deserialize_json(Integer, Box(1)), 1)

    def test_serialize_json(self):
        with self.assertRaisesRegexp(ValidationError, "Expected data, found None"):
            serialize_json(Integer, None)
        with self.assertRaisesRegexp(ValidationError, "Expected None, found data"):
            serialize_json(None, 1)
        self.assertEqual(serialize_json(None, None), None)
        self.assertEqual(serialize_json(Integer, 1).datum, 1)

    def test_string_to_json(self):
        self.assertEqual(string_to_json(""), None)
        self.assertEqual(string_to_json("1").datum, 1)

    def test_json_to_string(self):
        self.assertEqual(json_to_string(None), "")
        self.assertEqual(json_to_string(Box(1)), "1")
