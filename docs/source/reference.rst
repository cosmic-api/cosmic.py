Reference
=========

APIs
----

.. module:: cosmic.api

.. autoclass:: cosmic.api.API
   :members:

.. data:: cosmic.api.API.actions

    In the :class:`cosmic.api.API` object, the actions are stored in
    an :class:`OrderedDict` in a private :data:`_actions` property::

        >>> mathy._actions
        OrderedDict([(u'add', <cosmic.actions.Action object at 0x9ca18ec>)])

    The standard way of accessing them, however, is through a proxy
    property :data:`actions`. Like so:

        >>> mathy.actions.add
        <cosmic.actions.Action object at 0x9ca18ec>

.. data:: cosmic.api.API.models

    Models are stored in the :data:`_models` property, but accessed through
    a proxy like so::

        >>> mathy.models.Number
        <class '__main__.Number'>

.. autoclass:: cosmic.models.BaseModel
   :members:

HTTP Endpoints
--------------

.. autoclass:: cosmic.http.SpecEndpoint

.. autoclass:: cosmic.http.ActionEndpoint

.. autoclass:: cosmic.http.GetByIdEndpoint

.. autoclass:: cosmic.http.CreateEndpoint

.. autoclass:: cosmic.http.UpdateEndpoint

.. autoclass:: cosmic.http.DeleteEndpoint

.. autoclass:: cosmic.http.GetListEndpoint

Exceptions
----------

.. automodule:: cosmic.exceptions

.. autoclass:: cosmic.exceptions.ModelNotFound
   :members:

.. autoclass:: cosmic.exceptions.SpecError
   :members:

Tools and Helpers
-----------------

.. automodule:: cosmic.tools
   :members:
   :undoc-members:

.. autoclass:: cosmic.types.URLParams
   :show-inheritance:
