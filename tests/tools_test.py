from unittest2 import TestCase

from cosmic.tools import *
from cosmic.types import *
from cosmic.exceptions import SpecError


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


class TestArgsToDatum(TestCase):
    def test_one_arg(self):
        res = args_to_datum("universe")
        self.assertEqual(res, "universe")

    def test_one_kwarg(self):
        res = args_to_datum(what="universe")
        self.assertEqual(res, {"what": "universe"})

    def test_many_kwargs(self):
        res = args_to_datum(what="universe", when="now")
        self.assertEqual(res, {"what": "universe", "when": "now"})

    def test_multiple_args(self):
        with self.assertRaises(SpecError):
            args_to_datum("universe", "now")

    def test_no_args_no_kwargs(self):
        self.assertEqual(args_to_datum(), None)

    def test_mixed_args_and_kwargs(self):
        with self.assertRaises(SpecError):
            args_to_datum("universe", when="now")


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
            assert_is_compatible(s, ("a", "b",), ())
        with self.assertRaisesRegexp(SpecError, "function argument"):
            assert_is_compatible(s, ("a",), ("b",))


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


class TestUnderscoreIdentifier(TestCase):
    def test_okay(self):
        validate_underscore_identifier('hello_world')

    def test_bad_character(self):
        # For some strange reason, assertRaisesRegext tries to decode
        # error string as ASCII, causing UnicodeDecodeError. WTF.
        e = None
        try:
            validate_underscore_identifier(u'hello_\ufffdorld')
        except SpecError as err:
            e = err
        if not e:
            raise Exception("Must raise SpecError")

    def test_start_end_with_underscore(self):
        with self.assertRaisesRegexp(SpecError, "cannot start or end"):
            validate_underscore_identifier(u'_private')
        with self.assertRaisesRegexp(SpecError, "cannot start or end"):
            validate_underscore_identifier(u'weird_')

    def test_two_underscores(self):
        with self.assertRaisesRegexp(SpecError, "consecutive underscores"):
            validate_underscore_identifier(u'what__what')


class TestSerializeJSON(TestCase):
    def test_falsy(self):
        self.assertEqual(serialize_json(Integer, 0).datum, 0)




