from __future__ import unicode_literals

import inspect
import json
import sys

from cosmic.exceptions import SpecError, APIError, AuthenticationError

from teleport import JSON, Struct, Box, Schema, ValidationError

class Namespace(object):
    """Essentially a sorted dictionary. Allows to reference actions or
    models as attributes and implements __all__ so that a Namespace
    instance can be treated as a module.
    """

    def __init__(self):
        self._list = []
        self._dict = {}

    def __iter__(self):
        return self._list.__iter__()

    @property
    def __all__(self):
        return self._dict.keys()

    def add(self, name, item):
        self._list.append(item)
        self._dict[name] = item

    def __getattr__(self, name):
        try:
            return self._dict[name]
        except KeyError:
            raise SpecError("%s is not defined" % name)


def get_arg_spec(func):
    """Calculate JSON schema spec for action. If function has no
    arguments, returns None.
    """
    # Based on the passed in function's arguments, there are three
    # choices:
    args, varargs, keywords, defaults = inspect.getargspec(func)
    if varargs or keywords:
        raise SpecError("Cannot define action with splats (* or **)")
    # No arguments
    if len(args) == 0:
        return None
    # One argument: accepts a single JSON object
    if len(args) == 1:
        return JSON()
    # Multiple arguments: accepts a JSON object with a property for
    # each argument, each property being of type 'json'
    props = []
    # Number of non-keyword arguments (required ones)
    numargs = len(args) - (len(defaults) if defaults else 0)
    for i, arg in enumerate(args):
        props.append({
            "name": unicode(arg),
            "schema": {"type": "json"},
            "required": i < numargs
        })
    return normalize_schema({"type": "struct", "fields": props})

def apply_to_func(func, data):
    """Applies a piece of normalized data to the user-defined action function
    based on its argument spec. The data is assumed to be normalized by a
    schema compatible with *func*. (see
    :func:`~cosmic.tools.schema_is_compatible`). Thus, no validation is
    performed.

    If *func* takes a single argument, *data* is passed in as is. If it takes
    multiple arguments, *data* is assumed to be a dict and is unpacked into
    the function arguments.

    If object is None, *func* is called with no arguments.
    """
    if data == None:
        return func()
    args, varargs, keywords, defaults = inspect.getargspec(func)
    if len(args) == 1:
        return func(data)
    # Number of non-keyword arguments (required ones)
    numargs = len(args) - (len(defaults) if defaults else 0)
    apply_args = []
    apply_kwargs = {}
    for i, arg in enumerate(args):
        # args
        if i < numargs:
            apply_args.append(data.pop(arg))
        # kwargs
        elif arg in data.keys():
            apply_kwargs[arg] = data.pop(arg)
    return func(*apply_args, **apply_kwargs)

def pack_action_arguments(*args, **kwargs):
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

def schema_is_compatible(general, detailed):
    """Given two JSON Schemas, checks if the detailed schema is
    compatible with the general schema. The general schema is a subset
    of JSON schema as returned by tools.get_arg_spec, the special
    schema is an arbitrary JSON schema as passed in by the user.
    """
    if isinstance(general, JSON):
        return True
    # If not "json", general has to be an "struct". Make sure detailed
    # is an object too
    if not isinstance(detailed, Struct):
        return False
    gprops = general.fields
    dprops = detailed.fields
    if len(gprops) != len(dprops):
        return False
    for i in range(len(gprops)):
        gp = gprops[i]
        dp = dprops[i]
        if gp["name"] != dp["name"] or gp["required"] != dp["required"]:
            return False
    return True




def normalize_schema(schema):
    """A convenience method for normalizing a JSON schema into a
    :class:`~cosmic.models.Schema` object.
    """
    schema = Schema().deserialize(schema)
    return schema


def normalize(schema, datum):
    """Schema is a JSON schema and datum is the JSON form of the data. Returns
    the data normalized against the schema.
    """
    normalizer = normalize_schema(schema)
    return normalizer.deserialize(datum)


def normalize_json(schema, datum):
    if schema and not datum:
        raise ValidationError("Expected Box, found None")
    if datum and not schema:
        raise ValidationError("Expected None, found Box")
    if schema and datum:
        return schema.deserialize(datum.datum)
    return None

def serialize_json(schema, datum):
    if schema and not datum:
        raise ValidationError("Expected data, found None")
    if datum and not schema:
        raise ValidationError("Expected None, found data")
    if schema and datum:
        return Box(schema.serialize(datum))
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
