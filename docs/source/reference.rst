Reference
=========

APIs
----

.. module:: cosmic.api

.. autoclass:: cosmic.api.API
   :members: create, load, get_rules, get_flask_app, run, action, model, context

.. autoclass:: cosmic.api.APIModel
   :members:

Actions
-------

.. module:: cosmic.actions

.. autoclass:: cosmic.actions.Action
   :members: from_func, get_view, __call__

Exceptions
----------

.. module:: cosmic.exceptions

.. autoclass:: cosmic.exceptions.JSONParseError
   :members:

.. autoclass:: cosmic.exceptions.ValidationError
   :members:

.. autoclass:: cosmic.exceptions.UnicodeDecodeValidationError
   :members:

.. autoclass:: cosmic.exceptions.HttpError
   :members:

.. autoclass:: cosmic.exceptions.APIError
   :members:

.. autoclass:: cosmic.exceptions.ClientError
   :members:

.. autoclass:: cosmic.exceptions.AuthenticationError
   :members:

Tools and Helpers
-----------------

.. automodule:: cosmic.tools
   :members:
   :undoc-members:
