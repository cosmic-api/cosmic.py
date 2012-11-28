#!/usr/bin/python

from setuptools import setup

with open("README.rst") as readme:
    long_description = readme.read()

setup(
    name = 'apio',
    version = "0.0.9",
    packages = ['apio'],
    description = 'Human-friendly APIs',
    license = "MIT",
    author_email = "alexei.boronine@gmail.com",
    long_description = long_description,
    install_requires = [
        "Flask==0.9",
        "jsonpointer==0.3",
        "requests==0.14.2",
        "mock==1.0.1",
        "jsonschema==0.7-patched",
    ],
    dependency_links = [
        "http://github.com/boronine/jsonschema/tarball\
/99389e514e138a31dee09ca86e8c76db282ea1fa#egg=jsonschema-0.7-patched"
    ]
)
