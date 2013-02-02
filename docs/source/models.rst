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
object will provide a :meth:`normalize` method. This method will take
JSON data as provided by :func:`json.loads` and either return the
normalized data or raise a
:class:`~cosmic.exceptions.ValidationError`. Here is the basic usage
with a shortcut function, :func:`~cosmic.tools.normalize`::

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

A *model* is a data type definition in the form of a Python class, a
subclass of :class:`~cosmic.models.Model`. A model instance can be
serialized to JSON and the class must provide a method to instantiate
it from JSON. This method must also validate the model. You will find
that a lot of Cosmic internal classes are actually models.

Let's start with a minimal implementation::

    >>> from cosmic.models import Model
    >>> class Animal(Model):
    ...     schema = {"type": "string"}
    ... 

There are two ways to instantiate this model, depending on whether you
want your input validated. If the data is internally generated or has
already been validated, use the model's constructor. If your input if
coming from an untrusted source, use the model's
:meth:`~cosmic.models.Model.from_json` static method::

   >>> tiger = Animal.from_json("tiger")
   >>> tiger.serialize()
   u'tiger'
   >>> Animal.from_json(21)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/models.py", line 23, in from_json
        datum = schema.normalize(datum)
      File "cosmic/models.py", line 190, in normalize
        raise ValidationError("Invalid string", datum)
    cosmic.exceptions.ValidationError: Invalid string: 21

If the schema validation passes, the normalized data will be passed
into :meth:`~cosmic.models.Model.validate` for second-stage
validation. The reason :meth:`validate` is a class method is to make
sure no model gets instantiated until the data is validated::

    >>> class Beatle(Model):
    ...     schema = {"type": "string"}
    ...     @classmethod
    ...     def validate(cls, datum):
    ...         if datum not in ["John", "Paul", "George", "Ringo"]:
    ...             raise ValidationError("Beatle Not Found", datum)
    ...         return datum
    ... 
    >>> ringo = Beatle.from_json("Ringo")
    >>> yoko = Beatle.from_json("Yoko")
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/models.py", line 25, in from_json
        datum = cls.validate(datum)
      File "<stdin>", line 6, in validate
    cosmic.exceptions.ValidationError: Beatle Not Found: u'Yoko'

Most of the time, a model will be represented by a JSON object rather
than a primitive type like a string. In those cases you may want to
subclass :class:`cosmic.models.ObjectModel`, which will simplify you
schema definition by asking directly for a list of properties::

    >>> class Recipe(ObjectModel):
    ...     properties = [
    ...             {
    ...                     "name": "name",
    ...                     "required": True,
    ...                     "schema": {"type": "string"}
    ...             },
    ...             {
    ...                     "name": "spicy",
    ...                     "required": False,
    ...                     "schema": {"type": "boolean"}
    ...             }
    ...     ]
    ... 
    >>> poutine = Recipe.from_json({"name": "Poutine"})

As an added benefit, you can now access these properties directly::

    >>> poutine.spicy = True
    >>> poutine.name
    u'Poutine'
