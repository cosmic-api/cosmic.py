
=========
cosmic.py
=========

The canonical implementation of `Cosmic <http://www.cosmic-api.com/>`_.

Testing
-------

The only Python package that needs to be installed globally is `Tox <http://testrun.org/tox/latest/>`_. All the dependencies, testing tools and documentation tools will be installed by Tox in virtual environments. Tox will test against Python 2.6, Python 2.7 and `PyPy <http://pypy.org/>`_. Python 2.7 virtual environment will have `coverage.py <http://nedbatchelder.com/code/coverage/>`_ installed for unit test coverage checking which will be reported in the terminal when you run Tox. Detailed HTML reports will be generated in the ``htmlcov`` directory.

.. code:: bash

    $ pip install tox
    $ tox

Usually it will suffice to run:

.. code:: bash

    $ tox -e py27

However, before committing, you should make sure that Python 2.6 and PyPy work as well.

Building documentation
----------------------

Documentation is built using Sphinx, which is going to be installed by Tox in the Python 2.7 virtual environment.

.. code:: bash

    $ make docs

The output will be in ``docs/build/html``.

License
-------

Copyright (C) 2012 8313547 Canada Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
