from __future__ import unicode_literals

import re
import inspect
import json

from .exceptions import SpecError

from .types import *


class GetterNamespace(object):
    """An object that exposes an arbitrary mapping as a namespace, letting its
    values be accessible as attributes.

    :param get_item: a function that takes a string and returns an item
    :param get_all: a function that returns a list of all keys in the
                    namespace

    Example::

        >>> d = {"a": 1, "b": 2}
        >>> n = GetterNamespace(d.__getitem__, d.keys)
        >>> n.a
        1
        >>> n.__all__
        [u'a', u'b']

    """

    def __init__(self, get_item, get_all=None):
        self.get_item = get_item
        self.get_all = get_all

    def __getattr__(self, name):
        return self.get_item(name)

    @property
    def __all__(self):
        return self.get_all()


def get_args(func):
    """Given a function, returns a tuple (*required*, *optional*), tuples of
    non-keyword and keyword arguments respectively. If a function contains
    splats (\* or \**), a :exc:`~cosmic.exceptions.SpecError` will be raised.
    """
    args, varargs, keywords, defaults = inspect.getargspec(func)
    if varargs or keywords:
        raise SpecError("Cannot define action with splats (* or **)")
    # No arguments
    if len(args) == 0:
        return ((), (),)
    # Number of non-keyword arguments (required ones)
    numargs = len(args) - (len(defaults) if defaults else 0)
    required = tuple(args[:numargs])
    optional = tuple(args[numargs:])
    return (required, optional,)


def args_to_datum(*args, **kwargs):
    """Takes arbitrary args and kwargs and packs them into a dict if there are
    more than one. Returns `None` if there are no arguments. Must be called
    with either a single argument or multiple keyword arguments.
    """
    if len(args) == 1 and len(kwargs) == 0:
        return args[0]
    if len(args) == 0 and len(kwargs) > 0:
        return kwargs
    if len(args) == 0 and len(kwargs) == 0:
        return None
    raise SpecError("Action must be called either with one argument or with one or more keyword arguments")


def assert_is_compatible(schema, required, optional):
    """Raises a :exc:`~cosmic.exceptions.SpecError` if function argument spec
    (as returned by :func:`get_args`) is incompatible with the given schema.
    By incompatible, it is meant that there exists such a piece of data that
    is valid according to the schema, but that could not be applied to the
    function by :func:`apply_to_func`.
    """
    # No arguments
    if len(required + optional) == 0:
        raise SpecError("Function needs to accept arguments")
    # One argument can accept anything
    if len(required + optional) == 1:
        return
    # Multiple arguments means schema must be Struct
    if not isinstance(schema, Struct):
        raise SpecError("For a function that takes arguments, accepts schema"
                        " is expected to be a Struct")
    # Each non-keyword argument in the function must have a corresponding
    # required field in the schema
    for r in required:
        if r not in schema.param.keys() or not schema.param[r]["required"]:
            raise SpecError("Action argument '%s' must have a corresponding"
                            " required field in the accepts schema" % r)
    # All fields in the schema must have a corresponding function argument
    for f in schema.param.keys():
        if f not in set(required + optional):
            raise SpecError("The '%s' field must have a corresponding"
                            " function argument" % f)


def deserialize_json(schema, datum):
    if schema and not datum:
        raise ValidationError("Expected Box, found None")
    if datum and not schema:
        raise ValidationError("Expected None, found Box")
    if schema and datum:
        return schema.from_json(datum.datum)
    return None

def serialize_json(schema, datum):
    if schema is not None and datum is None:
        raise ValidationError("Expected data, found None")
    if datum is not None and schema is None:
        raise ValidationError("Expected None, found data")
    if schema is not None and datum is not None:
        return Box(schema.to_json(datum))
    return None

def string_to_json(s):
    if s == "":
        return None
    else:
        return Box(json.loads(s))

def json_to_string(box):
    if box == None:
        return ""
    return json.dumps(box.datum)


def validate_underscore_identifier(id):
    if re.match('^[a-zA-Z0-9_]*$', id) is None:
        raise SpecError("Identifier must consist of [a-zA-Z0-9_] characters only: %s" % id)
    if id.startswith('_') or id.endswith('_'):
        raise SpecError("Identifier cannot start or end with an underscore: %s" % id)
    if '__' in id:
        raise SpecError("Identifier cannot have consecutive underscores: %s" % id)

def is_string_type(serializer):
    if Schema.to_json(serializer)['type'] == 'String':
        return True
    if hasattr(serializer, 'schema'):
        return is_string_type(serializer.schema)
    return False
