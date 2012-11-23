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
