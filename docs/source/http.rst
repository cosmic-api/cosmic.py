HTTP Layer
==========

This implementation of Cosmic provides a thin HTTP layer. This allows us to
abstract the `Flask <http://flask.pocoo.org/>`_ dependency into a single
module, ``plugins.py``. In the future we are planning to support `Django
<https://www.djangoproject.com/>`_ as well as Flask. This architecture should
make it quite easy.

.. module:: cosmic.http

.. autoclass:: Request
   :members:

.. autoclass:: JSONRequest
   :show-inheritance:
   :members:

.. autoclass:: Response
   :members:
