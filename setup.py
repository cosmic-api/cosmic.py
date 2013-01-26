#!/usr/bin/python

from setuptools import setup

with open("README.rst") as readme:
    long_description = readme.read()

setup(
    name = 'cosmic',
    version = "0.0.1",
    packages = ['cosmic'],
    description = 'Human-friendly APIs',
    license = "MIT",
    author_email = "alexei.boronine@gmail.com",
    long_description = long_description,
    install_requires = [
        "Flask==0.9",
        "jsonpointer==0.3",
        "requests==0.14.2",
        "mock==1.0.1"
    ]
)
