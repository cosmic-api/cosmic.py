#!/usr/bin/python"""
"""
Cosmic
------

Cosmic is a tiny web API framework based on
`Teleport <http://www.cosmic-api.com/docs/teleport/spec/latest/>`_.

Links
`````

* `Website <http://www.cosmic-api.com/>`_
* `Documentation <http://www.cosmic-api.com/docs/cosmic/python/latest/>`_
* `Development version <https://github.com/cosmic-api/cosmic.py>`_

"""

from setuptools import setup

import os
root = os.path.abspath(os.path.dirname(__file__))

with open("{}/LICENSE".format(root)) as license_file:
    license_text = license_file.read()
with open("{}/CHANGES.rst".format(root)) as changes_file:
    changelog_text = changes_file.read()

long_description = """
{}

License
```````

{}

Changelog
`````````

{}
""".format(__doc__, license_text, changelog_text)

setup(
    name='cosmic',
    version="0.4.2",
    url='http://www.cosmic-api.com/docs/cosmic/python/',
    packages=['cosmic'],
    description='A tiny web API framework based on Teleport',
    license='MIT',
    author='8313547 Canada Inc.',
    author_email='alexei@boronine.com',
    long_description=long_description,
    install_requires=[
        'teleport>=0.2.1',
        'Werkzeug>=0.9.1',
        'requests>=2.2.0',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
)
