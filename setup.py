#!/usr/bin/python

from distutils.core import setup

with open("README.md") as readme:
    long_description = readme.read()

setup(
    name = 'apio',
    version = "0.0.1",
    packages = ['apio'],
    description = 'Human-friendly APIs',
    license = "MIT",
    author_email = "alexei.boronine@gmail.com",
    url = "http://github.com/boronine/pyhusl",
    long_description = long_description
)
