#!/usr/bin/python

from setuptools import setup

with open("README.rst") as readme:
    long_description = readme.read()

setup(
    name = 'cosmic',
    version = "0.0.4",
    url = "http://www.cosmic-api.com/docs/cosmic/python/",
    packages = ['cosmic'],
    description = 'A high-level web API framework',
    license = "MIT",
    author = "8313547 Canada Inc.",
    author_email = "alexei.boronine@gmail.com",
    long_description = long_description,
    install_requires = [
        "teleport==0.1.0",
        "Flask==0.9",
        "requests==0.14.2",
    ]
)
