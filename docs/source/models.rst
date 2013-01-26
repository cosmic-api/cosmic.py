Model System
============

Cosmic ships with a simple JSON-based schema and model system. A JSON
schema is a way of describing JSON data for validation and generating
documentation. A model is a Python class attached to a schema that may
contain extra validation functionality. Once a model is created, any
JSON schema can reference it by its name.

JSON Schema
-----------

A *schema* is a recursive JSON structure that mirrors the structure of
the data is is meant to validate.

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

    Because Cosmic must be extremely portable, it is essential that we
    keep the feature list to a minimum. In this instance, the minimum
    is generating documentation and basic validation of data structure
    and types. Instead of making you learn a new `DSL
    <http://en.wikipedia.org/wiki/Domain-specific_language>`_ for
    obscure validation, we encourage you to use the power of your
    language. The benefits of describing schemas in minute detail are
    greatly outweighed by the costs of growing the amount of code that
    needs to be ported.

When a JSON representation of a schema gets compiled, the resulting
object (an instance of :class:`~cosmic.models.Schema`) will provide a
:meth:`normalize` method. This method will take JSON data as provided
by :func:`json.loads` and either return the normalized data or
raise a :class:`~cosmic.exceptions.ValidationError`. Here is the basic
usage with a shortcut function, :func:`~cosmic.tools.normalize`::

    >>> from cosmic.tools import normalize
    >>> normalize({"type": "integer"}, 1)
    1
    >>> normalize({"type": "integer"}, 1.1)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/tools.py", line 147, in normalize
        return normalizer.normalize(datum)
      File "cosmic/models.py", line 103, in normalize
        raise ValidationError("Invalid integer", datum)
    cosmic.exceptions.ValidationError: Invalid integer: 1.1

A schema is always a Python dict. It must always contain the *type*
attribute. Here is a list of simple types you can use just like in the
above example:

+-------------------------+-------------+-------------+
|         Schema          |  JSON type  | Python type |  
+=========================+=============+=============+
| ``{"type": "integer"}`` | ``number``  | ``int``     |
+-------------------------+-------------+-------------+
| ``{"type": "float"}``   | ``number``  | ``float``   |
+-------------------------+-------------+-------------+
| ``{"type": "string"}``  | ``string``  | ``unicode`` |
+-------------------------+-------------+-------------+
| ``{"type": "boolean"}`` | ``boolean`` | ``bool``    |
+-------------------------+-------------+-------------+

An object schema must always contain a *properties* attribute, which
will be an array of property objects::

    >>> schema = {
    ...     "type": "object",
    ...     "properties": [
    ...         {
    ...             "name": "id",
    ...             "schema": {"type": "integer"},
    ...             "required": True
    ...         },
    ...         {
    ...             "name": "title",
    ...             "schema": {"type": "string"},
    ...             "required": False
    ...         }
    ...     ]
    ... }
    ...
    >>> normalize(schema, {"id": 1, "title": "Chameleon"})
    {u'id': 1, u'title': u'Chameleon'}
    >>> normalize(schema, {"id": 1})
    {u'id': 1}
    >>> normalize(schema, {"id": "Chameleon"})
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/tools.py", line 147, in normalize
        return normalizer.normalize(datum)
      File "cosmic/models.py", line 241, in normalize
        ret[prop] = schema.normalize(datum[prop])
      File "cosmic/models.py", line 103, in normalize
        raise ValidationError("Invalid integer", datum)
    cosmic.exceptions.ValidationError: Item at [u'id'] Invalid integer: 'Chameleon'

An array schema must always contain an *items* property, which must be
a *schema* that describes every item in the array. Here is a schema
describing an array or strings:

    >>> schema = {
    ...     "type": "array",
    ...     "items": {"type": "string"}
    ... }
    ...
    >>> normalize(schema, ["foo", "bar"])
    [u'foo', u'bar']
    >>> normalize(schema, [])
    []

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


