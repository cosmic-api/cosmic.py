.. image:: https://travis-ci.org/cosmic-api/cosmic.py.svg?branch=master
   :target: https://travis-ci.org/cosmic-api/cosmic.py

Testing
-------

The only Python package that needs to be installed globally is
`Tox <http://testrun.org/tox/latest/>`_. All the dependencies, testing tools
and documentation tools will be installed by Tox in virtual environments. Tox
will test against Python 2.7 and `PyPy <http://pypy.org/>`_. Python 2.7 virtual
environment will have `coverage.py <http://nedbatchelder.com/code/coverage/>`_
installed for unit test coverage checking which will be reported in the
terminal when you run Tox. Detailed HTML reports will be generated in the
``htmlcov`` directory.

.. code:: bash

    $ pip install tox
    $ tox

Usually it will suffice to run:

.. code:: bash

    $ tox -e py27

However, before committing, you should make sure that PyPy works as well.

Building documentation
----------------------

Documentation is built using Sphinx, which is going to be installed by Tox in
the Python 2.7 virtual environment.

.. code:: bash

    $ make docs

The output will be in ``docs/build/html``.
