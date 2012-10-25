#!/usr/bin/python

# Use setuptools if we can
try:
    from setuptools.core import setup
except ImportError:
    from distutils.core import setup
from apio import __version__

setup(
    name = 'apio',
    version = __version__,
    description = 'Human-friendly APIs',
    license = "MIT",
    author_email = "alexei.boronine@gmail.com",
    url = "http://github.com/boronine/pyhusl",
    test_suite = "tests.apio_test"
)
