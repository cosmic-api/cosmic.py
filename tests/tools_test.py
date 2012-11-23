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
        self.assertEqual(apply_to_action_func(f), "okay")

    def test_no_arg_fail(self):
        def f(): return "okay"
        with self.assertRaises(SpecError):
            apply_to_action_func(f, "oops")
    
    def test_one_arg_okay(self):
        def f(a): return a
        self.assertEqual(apply_to_action_func(f, 1), 1)

    def test_one_arg_fail(self):
        with self.assertRaises(SpecError):
            def f(a): return a
            apply_to_action_func(f)
            
    def test_one_kwarg_okay(self):
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, 1), 1)
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, {}), {})
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f), 2)

    def test_one_kwarg_passed_none(self):
        # None is an explicit value
        def f(a=2): return a
        self.assertEqual(apply_to_action_func(f, None), None)

    def test_multiple_args_and_kwargs_okay(self):
        def f(a, b=1): return a, b
        self.assertEqual(apply_to_action_func(f, {'a': 2}), (2, 1,))
        def f(a, b=1): return a, b
        self.assertEqual(apply_to_action_func(f, {'a': 2, 'b': 2}), (2, 2,))

    def test_multiple_kwargs_okay(self):
        def f(a=5, b=1): return a, b
        self.assertEqual(apply_to_action_func(f, {}), (5, 1,))

    def test_unknown_kwarg(self):
        with self.assertRaises(SpecError):
            def f(a=5, b=1): return a, b
            apply_to_action_func(f, {'c': 4})
    
    def test_not_an_object(self):
        with self.assertRaises(SpecError):
            def f(a=5, b=1): return a, b
            apply_to_action_func(f, "hello")

    def test_missing_required_arg(self):
        with self.assertRaises(SpecError):
            def f(a, b=1): return a, b
            apply_to_action_func(f, {})

class TestSerializeActionArguments(TestCase):

    def test_one_arg(self):
        self.assertEqual(serialize_action_arguments("universe"), "universe")
    
    def test_one_kwarg(self):
        self.assertEqual(serialize_action_arguments(what="universe"), {"what": "universe"})

    def test_many_kwargs(self):
        ser = serialize_action_arguments(what="universe", when="now")
        self.assertEqual(ser, {"what": "universe", "when": "now"})

    def test_multiple_args(self):
        with self.assertRaises(SpecError):
            serialize_action_arguments("universe", "now")

    def test_no_args_no_kwargs(self):
        with self.assertRaises(InvalidCallError):
            serialize_action_arguments()

    def test_mixed_args_and_kwargs(self):
        with self.assertRaises(SpecError):
            serialize_action_arguments("universe", when="now")
