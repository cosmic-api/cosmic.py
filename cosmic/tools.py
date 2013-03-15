from __future__ import unicode_literals

import inspect
import json
import sys

from cosmic.exceptions import SpecError, ValidationError, APIError, AuthenticationError
from cosmic.models import *

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
        return normalize_schema({"type": "json"})
    # Multiple arguments: accepts a JSON object with a property for
    # each argument, each property being of type 'json'
    props = []
    # Number of non-keyword arguments (required ones)
    numargs = len(args) - (len(defaults) if defaults else 0)
    for i, arg in enumerate(args):
        props.append({
            "name": arg,
            "schema": {"type": "json"},
            "required": i < numargs
        })
    return normalize_schema({"type": "object", "properties": props})

def apply_to_func(func, data):
    """Applies a normalized object to the user-defined action function based
    on its argument spec. If object is None, function is called with no
    arguments.
    """
    args, varargs, keywords, defaults = inspect.getargspec(func)
    if len(args) == 0:
        if data:
            raise SpecError("%s takes no arguments" % func.__name__)
        return func()
    if len(args) == 1:
        # We weren't passed a value
        if data == None:
            # Function does not have defaults but we weren't passed a
            # value
            if not defaults:
                raise SpecError("%s takes one argument" % func.__name__)
            # We weren't passed a value, but there's a default
            return func()
        # We were passed a value, safe to apply regardless of defaults
        return func(data)
    # func takes multiple arguments, make sure we have something to
    # work with..
    if type(data) != dict:
        raise SpecError("%s expects an object, got %s instead" % (func.__name__, type(data)))
    # Number of non-keyword arguments (required ones)
    numargs = len(args) - (len(defaults) if defaults else 0)
    apply_args = []
    apply_kwargs = {}
    for i, arg in enumerate(args):
        # args
        if i < numargs:
            if arg not in data.keys():
                raise SpecError("%s is a required argument" % arg)
            apply_args.append(data.pop(arg))
        # kwargs
        elif arg in data.keys():
            apply_kwargs[arg] = data.pop(arg)
    # Some stuff still remaining in the object?
    if data:
        raise SpecError("Unknown arguments: %s" % ", ".join(data.keys()))
    return func(*apply_args, **apply_kwargs)

def pack_action_arguments(*args, **kwargs):
    """Takes arbitrary args and kwargs and packs them into a dict if there are
    more than one. Returns `None` if there are no arguments.
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
    if isinstance(general, JSONDataSchema):
        return True
    # If not "json", general has to be an "object". Make sure detailed
    # is an object too
    if not isinstance(detailed, ObjectSchema):
        return False
    gprops = general.data['properties']
    dprops = detailed.data['properties']
    if len(gprops) != len(dprops):
        return False
    for i in range(len(gprops)):
        gp = gprops[i]
        dp = dprops[i]
        if gp["name"] != dp["name"] or gp["required"] != dp["required"]:
            return False
    return True




def fetch_model(full_name):
    if full_name == "cosmic.API":
        from cosmic.api import API
        return API
    if full_name == "cosmic.APIModel":
        from cosmic.api import APIModel
        return APIModel
    if full_name == "cosmic.Action":
        from cosmic.actions import Action
        return Action
    api_name, model_name = full_name.split('.', 1)
    try:
        api = sys.modules['cosmic.registry.' + api_name]
    except KeyError:
        raise ValidationError("Unknown API", api_name)
    try:
        return getattr(api.models, model_name)
    except SpecError:
        raise ValidationError("Unknown model for %s API" % api_name, model_name)


def normalize_schema(schema):
    return Schema.normalize(schema, fetcher=fetch_model)


def normalize(schema, datum):
    """Schema is expected to be a valid schema and datum is expected
    to be the return value of json.loads
    """
    normalizer = normalize_schema(schema)
    return normalizer.normalize_data(datum, fetcher=fetch_model)

