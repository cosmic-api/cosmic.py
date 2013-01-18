from __future__ import unicode_literals

import sys

from apio.exceptions import ValidationError, UnicodeDecodeValidationError, SpecError


class Model(object):
    schema = {"type": "any"}
    def __init__(self, data):
        schema = normalize_schema(self.schema)
        self.data = schema(data)
        self.validate()
    def validate(self):
        pass


def normalize_wildcard(datum):
    """Return *datum* without any normalization."""
    # Hack to make sure we don't end up with non-unicode strings in
    # normalized data
    if type(datum) == str:
        return normalize_string(datum)
    if type(datum) == list:
        return [normalize_wildcard(item) for item in datum]
    if type(datum) == dict:
        ret = {}
        for key, value in datum.items():
            ret[key] = normalize_wildcard(value)
        return ret
    return datum
normalize_wildcard.schema = {"type": "any"}

def normalize_integer(datum):
    """If *datum* is an integer, return it; if it is a float with a 0
    for its fractional part, return the integer part as an
    integer. Otherwise, raise a :exc:`ValidationError`.
    """
    if type(datum) == int:
        return datum
    if type(datum) == float and datum.is_integer():
        return int(datum)
    raise ValidationError("Invalid integer: %s" % (datum,))
normalize_integer.schema = {"type": "integer"}

def normalize_float(datum):
    """If *datum* is a float, return it; if it is an integer, cast it
    to a float and return it. Otherwise, raise a
    :exc:`ValidationError`.
    """
    if type(datum) == float:
        return datum
    if type(datum) == int:
        return float(datum)
    raise ValidationError("Invalid float: %s" % (datum,))
normalize_float.schema = {"type": "float"}

def normalize_string(datum):
    """If *datum* is a unicode string, return it. If it is a string,
    decode it as UTF-8 and return the result. Otherwise, raise a
    :exc:`ValidationError`. Unicode errors are dealt with strictly by
    raising :exc:`UnicodeDecodeValidationError`, a subclass of the
    above.
    """
    if type(datum) == unicode:
        return datum
    if type(datum) == str:
        try:
            return datum.decode('utf_8')
        except UnicodeDecodeError as inst:
            raise UnicodeDecodeValidationError(unicode(inst))
    raise ValidationError("Invalid string: %s" % (datum,))
normalize_string.schema = {"type": "string"}

def normalize_boolean(datum):
    """If *datum* is a boolean, return it. Otherwise, raise a
    :exc:`ValidationError`.
    """
    if type(datum) == bool:
        return datum
    raise ValidationError("Invalid boolean: %s" % (datum,))
normalize_boolean.schema = {"type": "boolean"}

def normalize_array(datum, items):
    """If *datum* is a list, construct a new list by running the
    *items* normalization function on each element of *datum*. This
    normalization function may raise :exc:`ValidationError`. If
    *datum* is not a list, :exc:`ValidationError` will be raised.

    .. code::

        >>> normalize_array([1.0, 2, 3.0], normalize_integer)
        [1, 2, 3]

    """
    if type(datum) == list:
        return [items(item) for item in datum]
    raise ValidationError("Invalid array: %s" % (datum,))

def normalize_object(datum, properties):
    """If *datum* is a dict, normalize it against *properties* and
    return the resulting dict. Otherwise raise a
    :exc:`ValidationError`.

    *properties* must be a list of dicts, where each dict has three
    attributes: *name*, *required* and *schema*. *name* is a string
    representing the property name, *required* is a boolean specifying
    whether the *datum* needs to contain this property in order to
    pass validation and *schema* is a normalization function.

    .. code::

        >>> normalize_object({"spicy": True}, [{
        ...    "name": "spicy",
        ...    "required": True,
        ...    "schema": normalize_boolean
        ... }])
        {"spicy": True}

    A :exc:`ValidationError` will be raised if:

    1. *datum* is missing a required property
    2. *datum* has a property not declared in *properties*.
    3. One of the properties of *datum* does not pass validation as defined
       by the corresponding *schema* value.

    """
    if type(datum) == dict:
        ret = {}
        required = {}
        optional = {}
        for prop in properties:
            if prop["required"] == True:
                required[prop["name"]] = prop["schema"]
            else:
                optional[prop["name"]] = prop["schema"]
        missing = set(required.keys()) - set(datum.keys())
        if missing:
            raise ValidationError("Missing properties: %s" % list(missing))
        extra = set(datum.keys()) - set(required.keys() + optional.keys())
        if extra:
            raise ValidationError("Unexpected properties: %s" % list(extra))
        for prop, schema in optional.items() + required.items():
            if prop in datum.keys():
                ret[prop] = schema(datum[prop])
        return ret
    raise ValidationError("Invalid object: %s" % (datum,))


def _normalize_property(datum):
    return normalize_object(datum, [
        {
            "name": "name",
            "required": True,
            "schema": normalize_string
        },
        {
            "name": "required",
            "required": True,
            "schema": normalize_boolean
        },
        {
            "name": "schema",
            "required": True,
            "schema": normalize_schema
        }
    ])

def _normalize_array_of_properties(datum):
    return normalize_array(datum, _normalize_property)

def normalize_schema(datum):
    """Given a JSON representation of a schema, return a function that
    will normalize data against that schema.

    For primitive types, it returns one of the simple normalization
    functions defined in this module::

        >>> normalizer = normalize_schema({"type": "integer"})
        >>> normalizer(1.0)
        1
        >>> normalizer == normalize_integer
        True

    For array or object types, it will build a custom function by
    wrapping :func:`normalize_array` or
    :func:`normalize_object`. These can be nested as deep as you want,
    :func:`normalize_schema` will recurse::

        >>> normalizer = normalize_schema({
        ...     "type": "array",
        ...     "schema": {"type": "float"}
        ... })
        >>> normalizer([1, 2.2, 3])
        [1.0, 2.2, 3.0]

    """
    if hasattr(datum, "schema"):
        return datum
    datum = normalize_object(datum, [
        {
            "name": "type",
            "required": True,
            "schema": normalize_string
        },
        {
            "name": "items",
            "required": False,
            "schema": normalize_schema
        },
        {
            "name": "properties",
            "required": False,
            "schema": _normalize_array_of_properties
        }
    ])
    st = datum["type"]
    # Then make sure the attributes are right
    if ((st == "array" and 'items' not in datum.keys()) or
        (st == "object" and 'properties' not in datum.keys()) or
        (st not in ["array", "object"] and len(datum) > 1) or
        (len(datum) == 3)):
        raise ValidationError("Invalid schema: %s" % datum)
    if st == "object":
        keys = [prop["name"] for prop in datum["properties"]]
        if len(set(keys)) < len(keys):
            raise ValidationError("Duplicate properties in schema: %s" % datum)
    # Just the type?
    if st == "any":
        return normalize_wildcard
    if st == "integer":
        return normalize_integer
    if st == "float":
        return normalize_float
    if st == "string":
        return normalize_string
    if st == "boolean":
        return normalize_boolean
    if st == "schema":
        return normalize_schema
    if '.' in st:
        api_name, model_name = st.split('.', 1)
        try:
            api = sys.modules['apio.index.' + api_name]
        except KeyError:
            raise ValidationError("Unknown API: %s" % api_name)
        try:
            model = getattr(api.models, model_name)
            def normalize_model(datum):
                if isinstance(datum, model):
                    return datum
                else:
                    return model(datum)
            return normalize_model
        except SpecError:
            raise ValidationError("Unknown model for %s API: %s" % (api_name, model_name))
    if st == "array":
        items = datum["items"]
        def normalize_custom_array(datum):
            return normalize_array(datum, items)
        normalize_custom_array.schema = {
            "type": "array",
            "items": items.schema
        }
        return normalize_custom_array
    if st == "object":
        properties = datum["properties"]
        def normalize_custom_object(datum):
            return normalize_object(datum, properties)
        normalize_custom_object.schema = {
            "type": "object",
            "properties": [{
                "name": prop["name"],
                "required": prop["required"],
                "schema": prop["schema"].schema
            } for prop in properties]
        }
        return normalize_custom_object
    raise ValidationError("Unknown type: %s" % st)
normalize_schema.schema = {"type": "schema"}

def serialize_json(datum):
    dt = type(datum)
    if dt in [int, bool, float, unicode]:
        return datum
    if dt is str:
        return datum.decode('utf_8')
    if dt == list:
        return [serialize_json(item) for item in datum]
    if dt == dict:
        ret = {}
        for key, value in datum.items():
            ret[key] = serialize_json(value)
        return ret
    if isinstance(datum, Model):
        return serialize_json(datum.data)
    if hasattr(datum, "schema"):
        return datum.schema

