Model System
============

.. important::
    This document is meant to get you started in Python. For a strict specification,
    consult `this page </documentation/models.html>`_.

Cosmic ships with a simple JSON-based schema and model system. A JSON schema
is a way of describing JSON data for validation and generating documentation.
A model is a Python class attached to a schema that may contain extra
validation functionality. Once a model is created, any JSON schema can
reference it by its name.

JSON Schema Basics
------------------

A *schema* is a recursive JSON structure that mirrors the structure of the
data it is meant to validate.

When a JSON representation of a schema gets compiled, the resulting object
will provide a :meth:`normalize_data` method. This method will take JSON data
as provided by :func:`json.loads` and either return the native data or raise a
:class:`~cosmic.exceptions.ValidationError`. Here is the basic usage with a
convenience function, :func:`~cosmic.tools.normalize_schema`::

    >>> from cosmic.tools import normalize_schema
    >>> s = normalize_schema({"type": "integer"})
    >>> s
    <cosmic.models.IntegerSchema object at 0x201a450>
    >>> s.normalize_data(1)
    1
    >>> s.normalize_data(1.1)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/tools.py", line 147, in normalize
        return normalizer.normalize(datum)
      File "cosmic/models.py", line 103, in normalize
        raise ValidationError("Invalid integer", datum)
    cosmic.exceptions.ValidationError: Invalid integer: 1.1

A schema is always a Python dict. It must always contain the *type* attribute.
Here is a list of simple types you can use just like in the above example:

+-------------------------+---------------------+---------------+
|         Schema          |  JSON type          | `Python type` |  
+=========================+=====================+===============+
| ``{"type": "integer"}`` | ``number``          | ``int``       |
+-------------------------+---------------------+---------------+
| ``{"type": "float"}``   | ``number``          | ``float``     |
+-------------------------+---------------------+---------------+
| ``{"type": "string"}``  | ``string``          | ``unicode``   |
+-------------------------+---------------------+---------------+
| ``{"type": "boolean"}`` | ``boolean``         | ``bool``      |
+-------------------------+---------------------+---------------+
| ``{"type": "binary"}``  | ``string`` (base64) | ``str``       |
+-------------------------+---------------------+---------------+

An object schema must always contain a *properties* attribute, which will be
an array of property objects::

    >>> s = normalize_schema({
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
    ... })
    ...
    >>> s.normalize_data({"id": 1, "title": "Chameleon"})
    {u'id': 1, u'title': u'Chameleon'}
    >>> s.normalize_data({"id": 1})
    {u'id': 1}
    >>> s.normalize_data({"id": "Chameleon"})
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/tools.py", line 147, in normalize
        return normalizer.normalize(datum)
      File "cosmic/models.py", line 241, in normalize
        ret[prop] = schema.normalize(datum[prop])
      File "cosmic/models.py", line 103, in normalize
        raise ValidationError("Invalid integer", datum)
    cosmic.exceptions.ValidationError: Item at [u'id'] Invalid integer: 'Chameleon'

An array schema must always contain an *items* property, which must be a
schema that describes every item in the array. Here is a schema describing an
array or strings:

    >>> s = normalize_schema({
    ...     "type": "array",
    ...     "items": {"type": "string"}
    ... })
    ...
    >>> s.normalize_data(["foo", "bar"])
    [u'foo', u'bar']
    >>> s.normalize_data([])
    []

Of course, these schemas can be nested as deep as you like. For example, to
validate ``[{"name": "Rose"}, {"name": "Lily"}]``, you could use the following
schema:

.. code:: python

    {
        "type": "array",
        "items": {
            "type": "object",
            "properties": [
                {
                    "name": "name",
                    "schema": {"type": "string"},
                    "required": True
                }
            ]
        }
    }

Models
------

A *model* is a data type definition in the form of a Python class, a subclass
of :class:`~cosmic.models.Model`. A model instance can be serialized to JSON
and the class must provide a method to instantiate it from JSON. This method
must also validate the model. You will find that a lot of Cosmic internal
classes are actually models.

Let's start with a minimal implementation::

    >>> from cosmic.models import Model
    >>> class Animal(Model):
    ...     schema = normalize_schema({"type": "string"})
    ... 

There are two ways to instantiate this model, depending on whether you want
your input validated or not. If the data is internally generated or has
already been validated, simply use the model's constructor. If your input is
coming from an untrusted source, use the model's
:meth:`~cosmic.models.Model.normalize` static method::

   >>> Animal.normalize(21)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/models.py", line 23, in from_json
        datum = schema.normalize(datum)
      File "cosmic/models.py", line 190, in normalize
        raise ValidationError("Invalid string", datum)
    cosmic.exceptions.ValidationError: Invalid string: 21

When instantiated, the native data will be put in the model instance's *data*
property::

    >>> tiger = Animal.normalize("Tiger")
    >>> tiger.data
    u'Tiger'

If the schema validation passes, the native data will be passed into
:meth:`~cosmic.models.Model.validate` for second-stage validation. By default,
this method does nothing.

.. code:: python

    >>> class Beatle(Model):
    ...     schema = normalize_schema({"type": "string"})
    ...     @classmethod
    ...     def validate(cls, datum):
    ...         if datum not in ["John", "Paul", "George", "Ringo"]:
    ...             raise ValidationError("Beatle Not Found", datum)
    ... 
    >>> ringo = Beatle.normalize("Ringo")
    >>> yoko = Beatle.normalize("Yoko")
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/models.py", line 25, in from_json
        datum = cls.validate(datum)
      File "<stdin>", line 6, in validate
    cosmic.exceptions.ValidationError: Beatle Not Found: u'Yoko'

An instance of a model class will have a
:meth:`~cosmic.models.Model.serialize` method::

    >>> ringo.serialize()
    u"Ringo"

Note that there is an equivalent way of calling this method::

    >>> Beatle.serialize(ringo)
    u"Ringo"

Internally, Cosmic prefers this syntax because it allows to represent
primitive types with model classes by implementing :meth:`serialize` as a
classmethod. These models are never instantiated, they are effectively just
namespaces holding two classmethods: :meth:`normalize` and :meth:`serialize`.
In general, :meth:`serialize` does not validate data, it can assume that its
input is in the same format as the output of the corresponding
:meth:`normalize` method.

Simple Builtin Models
~~~~~~~~~~~~~~~~~~~~~

Most JSON schema types are implemented as explained above. Note that all of
the classes below inherit :meth:`serialize` from
:class:`~cosmic.models.SimpleSchema`. The default implementation of this method
simply returns the given value.

.. autoclass:: cosmic.models.IntegerModel
   :members:

.. autoclass:: cosmic.models.FloatModel
   :members:

.. autoclass:: cosmic.models.StringModel
   :members:

.. autoclass:: cosmic.models.BinaryModel
   :members:

.. autoclass:: cosmic.models.BooleanModel
   :members:

.. autoclass:: cosmic.models.ArrayModel
   :members:

.. autoclass:: cosmic.models.ObjectModel
   :members:

.. _key-value-models:

Key-Value Models
~~~~~~~~~~~~~~~~

Most of the time, a model will be represented by a key-value structure rather
than a primitive type like a string. In those cases you may want to subclass
:class:`~cosmic.models.ClassModel`, which will simplify your schema
definition by asking directly for a list of properties::

    >>> class Recipe(ClassModel):
    ...     properties = [
    ...         {
    ...             "name": "name",
    ...             "required": True,
    ...             "schema": normalize_schema({"type": "string"})
    ...         },
    ...         {
    ...             "name": "spicy",
    ...             "required": False,
    ...             "schema": normalize_schema({"type": "boolean"})
    ...         }
    ...     ]
    ... 
    >>> poutine = Recipe.normalize({"name": "Poutine"})

As an added benefit, you can now access these properties directly::

    >>> poutine.spicy = True
    >>> poutine.name
    u'Poutine'

The real power of models comes from the fact that once they have been
registered with an :class:`~cosmic.api.API`, you can reference them from any
schema. If the above model was part of an API called ``cookbook``, we would be
able to reference it like so: ``{"type": "cookbook.Recipe"}``. When a JSON
object gets validated against such a schema, the returned value will be an
instance of :class:`Recipe`.

    >>> s = normalize_schema({"type": "cookbook.Recipe"})
    >>> s.normalize_data({"name": "kimchi"})
    <Recipe object at 0x297dc10>

When you reference a model belonging to your own API, Cosmic will call the
model's :meth:`~cosmic.models.Model.normalize` method in the background, and
thus run full validation on the data. If you reference a model belonging to a
third-party API, Cosmic will fetch the model schema from the registry,
dynamically create a class representing that model and try to instantiate it
by validating the data against the schema. Keep in mind that it will not be
able to run custom validation on the data, only basic schema validation.

Raw JSON Data
~~~~~~~~~~~~~

There is another type available in the JSON schema: ``json``. This type
represents arbitrary JSON data. No validation is performed. When normalized
against ``{"type": "json"}``, a JSON value will be wrapped by an instance of
:class:`~cosmic.models.JSONData`.

You may want to use this type as a wildcard when you don't know in advance
what the data will look like, or if you expect a separate system to deal with
it. Please avoid using it as a way of allowing multiple types for a property.
Each property should have just one type.

.. code:: python

    >>> thing = normalize({"type": "json"}, {"stuff": True})
    >>> thing
    <JSONData {"stuff": true}>
    >>> thing.data["stuff"]
    True

Schema Models
~~~~~~~~~~~~~

Schemas, the objects that normalize and serialize data, need to be normalized
and serialized themselves. In order to enable this, they are implemented as
models, validated against ``{"type": "schema"}``.

The class responsible for this type is :class:`~cosmic.models.Schema`.
Internally, its :meth:`normalize` method looks at the *type* attribute of the
data (which is expected to be a dict) and delegates the work to a more
specific class, like :class:`~cosmic.models.IntegerSchema`, by calling its own
:meth:`normalize` method::

    >>> from cosmic.models import Schema
    >>> s = Schema.normalize({"type": "integer"})
    >>> s
    <cosmic.models.IntegerSchema object at 0x1c518d0>
    >>> s.normalize_data(1.0)
    1

Please note that :class:`IntegerSchema`'s :meth:`normalize` classmethod
normalizes the schema itself (incidentally, the only acceptable value is
``{"type": "integer"}``), while its :meth:`normalize_data` method normalizes
the data it represents, namely an integer. :meth:`normalize_data` and
:meth:`serialize_data` simply call :class:`~cosmic.models.IntegerModel`'s
:meth:`normalize` and :meth:`serialize` methods.

As you can see, the ``schema`` type is quite handy. Not only is it used by the
model system internally but also by other modules in Cosmic. It allows such
things as actions to be implemented as simple models.

A Word About Null
-----------------

The only place where ``null`` is allowed within our JSON schema system is in a
``json`` model. Trying to pass a ``null`` as the value of an optional property
will result in a
:exc:`~cosmic.exceptions.ValidationError`, such a property should instead be
omitted from the payload.

The reason we wrap arbitrary JSON with a model rather than just
dump it is to avoid ambiguity between ``null`` as an explicit
value and ``None`` as an absense of value. There are a couple of
places where this ambiguity may cause confusion. Say you define a
model as follows::

    >>> class Thing(ObjectModel):
    ...     properties = [
    ...         {
    ...             "name": "stuff",
    ...             "required": False,
    ...             "schema": {"type": "json"}
    ...         }
    ...     ]

When its optional property is omitted, the value will be a plain
Python ``None``::

    >>> thing = Thing.normalize({})
    >>> thing.stuff is None
    True

However, when you pass in an explicit null value, the property will
be boxed::

    >>> thing = Thing.normalize({"stuff": None})
    >>> thing.stuff is None
    False
    >>> thing.stuff
    <JSONData null>
    >>> thing.stuff.data is None
    True

Here is a real-life example where this detail comes in handy. A
JSON HTTP request may either come with a payload or with an empty
body. A payload of ``null`` is different from an empty body, and
may have a subtly different meaning. Thus we need a way to
differentiate between them. Conveniently, the
:class:`~cosmic.models.JSONData` class responsible for the
``core`` model comes with a
:meth:`~cosmic.models.JSONData.from_string` method.

An empty string will yield a plain Python ``None`` value::

    >>> from cosmic.models import JSONData
    >>> JSONData.from_string("") is None
    True

But a ``null`` will yield a 'boxed' value::

    >>> JSONData.from_string("null")
    <JSONData null>

Extending The Model System
--------------------------

The model system is decoupled from the rest of Cosmic, it does not know
anything about APIs. When it encounters a namespaced type such as
``cookbook.Recipe``, it leaves a placeholder in place of the recipe model.
In order to fetch the actual recipe model, you must *resolve* the models
by passing in a model fetcher into :meth:`Schema.resolve`.

    >>> from cosmic.tools import fetch_model
    >>> schema = Schema.normalize({"type": "cookbook.Recipe"})
    >>> schema.resolve(fetcher=fetch_model)

You will rarely have to do this yourself if you stick to the convenience
functions provided in :mod:`cosmic.tools`: :func:`~cosmic.tools.normalize`
and :func:`~cosmic.tools.normalize_schema`.
