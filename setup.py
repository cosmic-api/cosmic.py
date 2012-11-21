#!/usr/bin/python

from setuptools import setup

with open("README.rst") as readme:
    long_description = readme.read()

setup(
    name = 'apio',
    version = "0.0.6",
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
/391916e71b946db3bf5d92cbb767f620a869fc82#egg=jsonschema-0.7-patched"
    ]
)
