#!/usr/bin/python

from setuptools import setup

with open("README.rst") as readme:
    long_description = readme.read()

setup(
    name = 'cosmic',
    version = "0.3.0.alpha1",
    url = "http://www.cosmic-api.com/docs/cosmic/python/",
    packages = ['cosmic'],
    description = 'A high-level web API framework',
    license = "MIT",
    author = "8313547 Canada Inc.",
    author_email = "alexei@boronine.com",
    long_description = long_description,
    install_requires = [
        "teleport==0.2.1",
        "Flask==0.10",
        "Werkzeug==0.9.1",
        "requests==2.0.0",
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
    ],
)
