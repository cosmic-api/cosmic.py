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

Types
-----

.. autoclass:: cosmic.types.Model
:show-inheritance:

.. autoclass:: cosmic.types.Link
:show-inheritance:

.. autoclass:: cosmic.types.Representation
:show-inheritance:

.. autoclass:: cosmic.types.Patch
:show-inheritance:

.. autoclass:: cosmic.types.URLParams
:show-inheritance:


HTTP Endpoints
--------------

.. autoclass:: cosmic.http.ActionEndpoint

.. autoclass:: cosmic.http.GetByIdEndpoint

.. autoclass:: cosmic.http.CreateEndpoint

.. autoclass:: cosmic.http.UpdateEndpoint

.. autoclass:: cosmic.http.DeleteEndpoint

.. autoclass:: cosmic.http.GetListEndpoint

Exceptions
----------

.. automodule:: cosmic.exceptions

.. autoclass:: cosmic.exceptions.SpecError
:members:

.. autoclass:: cosmic.exceptions.NotFound
:members:

.. autoclass:: cosmic.exceptions.HTTPError
:members:

.. autoclass:: cosmic.exceptions.RemoteHTTPError
:members:

Tools and Helpers
-----------------

.. automodule:: cosmic.tools
:members:
       :undoc-members:

