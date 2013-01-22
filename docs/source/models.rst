Model System
============

APIO ships with a simple JSON-based schema and model system. A JSON
schema is a way of describing JSON data for validation and generating
documentation. A model is a Python class attached to a schema that may
contain extra validation functionality. Once a model is created, any
JSON schema can reference it by its name.

JSON schema
-----------

We provide with a simple way to define the format of your data with a
schema written in JSON.

.. note::

    *Why invent our own JSON schema system?*
    
    Before deciding to go with our own system, we took a good look at
    some existing options. Our best candidates were `JSON Schema
    <http://json-schema.org/>`_ and `Apache Avro
    <http://avro.apache.org/>`_. JSON Schema has a significant flaw:
    the order of object attributes is not preserved. Apache Avro had a
    different problem: because an attribute can be defined as allowing
    multiple types, objects needed to be wrapped in an annotation
    layer to avoid ambiguity. Instead of ``{"name": "Jenn"}`` we would
    have to output ``{"Person": {"name": "Jenn"}}``. In the context of
    REST APIs, this is uncommon and potentially confusing.

    Because APIO must be extremely portable, it is essential that we
    keep the feature list to a reasonable minimum. In this instance,
    the minimum is generating documentation and basic validation of
    data structure and types. Instead of making you learn a new `DSL
    <http://en.wikipedia.org/wiki/Domain-specific_language>`_ for
    obscure validation, we encourage you to use the power of your
    language. The benefits of describing schemas in minute detail are
    greatly outweighed by the costs of growing the amount of code that
    needs to be ported.

A *schema* is always a Python dict. It must always contain the *type*
attribute. If you would like to validate a value as a string, you
would validate it against the ``{"type": "string"}`` schema. Here is a
list of all the types we support:

+-----------------+-------------+-------------+-------------------------------------+
| Schema ``type`` |  JSON type  | Python type | Notes                               |
+=================+=============+=============+=====================================+
| ``any``         |             |             | Wildcard. Will validate anything.   |
+-----------------+-------------+-------------+-------------------------------------+
| ``integer``     | ``number``  |   ``int``   | Will be encoded as a number with no |
|                 |             |             | decimal part. When parsing JSON, a  |
|                 |             |             | number with a decimal part is       |
|                 |             |             | acceptable as long as the decimal   |
|                 |             |             | part is 0. It will be cast to an    |
|                 |             |             | integer.                            |
+-----------------+-------------+-------------+-------------------------------------+
| ``float``       | ``number``  |  ``float``  | Will be encoded as a number with a  |
|                 |             |             | decimal part, even if that part is  |
|                 |             |             | 0. An integer will always pass      |
|                 |             |             | validation and will be cast to a    |
|                 |             |             | float.                              |
+-----------------+-------------+-------------+-------------------------------------+
| ``string``      | ``string``  | ``unicode`` | All strings are UTF-8.              |
|                 |             |             |                                     |
+-----------------+-------------+-------------+-------------------------------------+
| ``boolean``     | ``boolean`` |  ``bool``   |                                     |
+-----------------+-------------+-------------+-------------------------------------+
| ``object``      | ``object``  | ``dict``    | See below.                          |
+-----------------+-------------+-------------+-------------------------------------+
| ``array``       | ``array``   | ``list``    | See below.                          |
+-----------------+-------------+-------------+-------------------------------------+

An object schema must always contain a *properties* attribute, which
will be an array of property objects. Each property must have a name,
a schema that describes its value and a flag, signifying whether this
property is required or not. There cannot be two properties with the
same *name* in an object. The object validation succeeds unless a
required property is missing or a property's value doesn't validate
against its *schema*. Here is an example of a full object schema in
JSON:

.. code:: json

    {
        "type": "object",
        "properties": [
            {
                "name": "id",
                "schema": {"type": "integer"},
                "required": true
            },
            {
                "name": "title",
                "schema": {"type": "string"},
                "required": false
            }
        ]
    }

An array schema must always contain an *items* property, which must be
a *schema* that describes every item in the array. An empty array will
always pass validation. Here is a schema describing an array or
strings:

.. code:: json

    {
        "type": "array",
        "items": {"type": "string"}
    }

Of course, these schemas can be nested as deep as you like. For
example, to validate ``[{"name": "Rose"}, {"name": "Lily"}]``, you
could use the following schema:

.. code:: json

    {
        "type": "array",
        "items": {
            "type": "object",
            "properties": [
                {
                    "name": "name",
                    "schema": {"type": "string"},
                    "required": true
                }
            ]
        }
    }

The basic usage is as follows::

    >>> from apio.models import normalize_schema
    >>> normalizer = normalize_schema({"type": "integer"})
    >>> normalizer(3)
    3
    >>> normalizer(4.0)
    4
    >>> normalizer(4.1)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/lib/python2.7/site-packages/apio/models.py", line 16, in normalize_integer
        raise ValidationError("Invalid integer: %s" % (datum,))
    apio.exceptions.ValidationError: Invalid integer: 3.3

The :mod:`apio.models` module provides, first of all, a set of basic
functions for normalizing JSON primitives. These functions raise
:exc:`~apio.exceptions.ValidationError` if the value is invalid or
return a normalized version of the value if it is.

.. autofunction:: apio.models.normalize_wildcard

.. autofunction:: apio.models.normalize_integer

.. autofunction:: apio.models.normalize_float

.. autofunction:: apio.models.normalize_string

.. autofunction:: apio.models.normalize_boolean

.. autofunction:: apio.models.normalize_array

.. autofunction:: apio.models.normalize_object

These functions deal with simple JSON values, but :mod:`apio.models`
also provides a normalization function for *schemas*:

.. autofunction:: apio.models.normalize_schema

Models
------

Models are created for a particular :class:`~apio.api.API` by subclassing the
``MyCoolAPI.Model`` class. The act of subclassing will register the
model with the API and add it to the API spec. The default Model
schema is ``{"type": "any"}``. To change it, override the ``schema``
attribute.
