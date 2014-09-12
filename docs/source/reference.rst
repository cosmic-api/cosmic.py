Reference
=========

APIs
----

.. module:: cosmic.api

.. autoclass:: cosmic.api.BaseAPI

   .. autoinstanceattribute:: cosmic.api.BaseAPI.spec
      :annotation:

   .. autoinstanceattribute:: cosmic.api.BaseAPI.actions
      :annotation:

   .. autoinstanceattribute:: cosmic.api.BaseAPI.models
      :annotation:

.. autoclass:: cosmic.api.API
   :show-inheritance:
   :members:

Models
------

.. module:: cosmic.models

.. autoclass:: cosmic.models.BaseModel

   .. autoattribute:: cosmic.models.BaseModel.properties
      :annotation:

   .. autoattribute:: cosmic.models.BaseModel.links
      :annotation:

   .. autoattribute:: cosmic.models.BaseModel.methods
      :annotation:

   .. autoattribute:: cosmic.models.BaseModel.query_fields
      :annotation:

   .. autoattribute:: cosmic.models.BaseModel.list_metadata
      :annotation:

   .. automethod:: cosmic.models.BaseModel.get_by_id
   .. automethod:: cosmic.models.BaseModel.get_list
   .. automethod:: cosmic.models.BaseModel.create
   .. automethod:: cosmic.models.BaseModel.update
   .. automethod:: cosmic.models.BaseModel.delete
   .. automethod:: cosmic.models.BaseModel.validate_patch

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

.. autoclass:: cosmic.types.APISpec
   :show-inheritance:

Globals
-------

.. autoclass:: cosmic.globals.ThreadLocalDict

.. autofunction:: cosmic.globals.thread_local

.. autofunction:: cosmic.globals.thread_local_middleware

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

.. autoclass:: cosmic.exceptions.ThreadLocalMissing
   :members:

Tools and Helpers
-----------------

.. automodule:: cosmic.tools
   :members:
   :undoc-members:

