import inspect
import json

from apio.exceptions import SpecError, InvalidCallError, ValidationError

class Namespace(object):
    """Essentially a sorted dictionary. Allows to reference actions or
    models as attributes and implements __all__ so that a Namespace
    instance can be treated as a module.
    """

    def __init__(self):
        self._list = []
        self._dict = {}

    def __iter__(self):
        """Allow iterating through items"""
        return self._list.__iter__()

    @property
    def __all__(self):
        return self._dict.keys()

    @property
    def specs(self):
        return [item.spec for item in self._list]

    def add(self, name, item):
        self._list.append(item)
        self._dict[name] = item

    def __getattr__(self, name):
        try:
            return self._dict[name]
        except KeyError:
            raise SpecError("%s is not defined" % name)

class JSONPayload(object):
    def __init__(self, json):
        self.json = json
    @classmethod
    def from_string(cls, s):
        if s == "":
            return None
        return cls(json.loads(s))

def get_arg_spec(func):
    """Calculate JSON schema spec for action.  If function has no
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
        return { "type": "any" }
    # Multiple arguments: accepts a JSON object with a property for
    # each argument, each property being of type 'any'
    spec = {
        "type": "object",
        "properties": []
    }
    # Number of non-keyword arguments (required ones)
    numargs = len(args) - (len(defaults) if defaults else 0)

    for i, arg in enumerate(args):
        spec["properties"].append({
            "name": arg,
            "schema": {"type": "any"},
            "required": i < numargs
        })
    return spec

def apply_to_action_func(func, data):
    """Applies a JSONPayload object to the user-defined action
    function based on its argument spec. If data is None, function is
    called with no arguments.
    """
    args, varargs, keywords, defaults = inspect.getargspec(func)
    if len(args) == 0:
        if data:
            raise SpecError("%s takes no arguments" % func.__name__)
        return func()
    if len(args) == 1:
        # We weren't passed a value
        if not data:
            # Function does not have defaults but we weren't passed a
            # value
            if not defaults:
                raise SpecError("%s takes one argument" % func.__name__)
            # We weren't passed a value, but there's a default
            return func()
        # We were passed a value, safe to apply regardless of defaults
        return func(data.json)
    # func takes multiple arguments, make sure we have something to
    # work with..
    if not data or type(data.json) is not dict:
        raise SpecError("%s expects an object" % func.__name__)
    # Number of non-keyword arguments (required ones)
    numargs = len(args) - (len(defaults) if defaults else 0)
    apply_args = []
    apply_kwargs = {}
    for i, arg in enumerate(args):
        # args
        if i < numargs:
            if arg not in data.json.keys():
                raise SpecError("%s is a required argument" % arg)
            apply_args.append(data.json.pop(arg))
        # kwargs
        elif arg in data.json.keys():
            apply_kwargs[arg] = data.json.pop(arg)
    # Some stuff still remaining in the object?
    if data.json:
        raise SpecError("Unknown arguments: %s" % ", ".join(data.json.keys()))
    return func(*apply_args, **apply_kwargs)

def serialize_action_arguments(*args, **kwargs):
    """Takes arbitrary args and kwargs, serializes them into a
    JSONPayload object to be passed over the wire then deserialized by
    `apply_to_action_func`. If no arguments passed, returns None.
    """
    if len(args) == 1 and len(kwargs) == 0:
        return JSONPayload(args[0])
    if len(args) == 0 and len(kwargs) > 0:
        return JSONPayload(kwargs)
    if len(args) == 0 and len(kwargs) == 0:
        return None
    raise SpecError("Action must be called either with one argument or with one or more keyword arguments")

def schema_is_compatible(general, detailed):
    """Given two JSON Schemas, checks if the detailed schema is
    compatible with the general schema. The general schema is a subset
    of JSON schema as returned by tools.get_arg_spec, the special
    schema is an arbitrary JSON schema as passed in by the user.
    """
    if general["type"] == "any":
        return True
    # If not "any", general has to be an "object". Make sure detailed
    # is an object too
    if detailed["type"] != "object":
        return False
    if len(general["properties"]) != len(detailed["properties"]):
        return False
    for i in range(len(general["properties"])):
        gp = general["properties"][i]
        dp = detailed["properties"][i]
        if gp["name"] != dp["name"] or gp["required"] != dp["required"]:
            return False
    return True

def normalize(schema, datum):
    """Schema is expected to be a valid schema and datum is expected
    to be the return value of json.loads
    """
    st = schema["type"]
    dt = type(datum)
    # Wildcard
    if st == "any":
        return datum
    elif st == "integer":
        if dt == int:
            return datum
        # A float in place of an int is okay, as long as its
        # fractional part is 0
        if dt == float and datum.is_integer():
            return int(datum)
    elif st == "float":
        if dt == float:
            return datum
        # An int in place of a float is always okay, just cast it for
        # normalization's sake
        if dt == int:
            return float(datum)
    elif st == "string":
        if dt == unicode:
            return datum
        # Cast to unicode
        if dt == str:
            return unicode(datum)
    elif st == "boolean" and dt == bool:
        return datum
    elif st == "array" and dt == list:
        return [normalize(schema["items"], item) for item in datum]
    elif st == "object" and dt == dict:
        ret = {}
        required = {}
        optional = {}
        for prop in schema["properties"]:
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
                ret[prop] = normalize(schema, datum[prop])
        return ret
    # Validate schema type using META_SCHEMA
    elif st == "schema":
        # First test the basic structure by recursing
        normalized = normalize(META_SCHEMA, datum)
        prop_type = normalized["type"]
        # type is array if and only if items specified
        if (prop_type == "array") != ("items" in normalized.keys()):
            raise ValidationError("Invalid %s schema" % prop_type)
        # type is object if and only if properties specified
        if (prop_type == "object") != ("properties" in normalized.keys()):
            raise ValidationError("Invalid %s schema" % prop_type)
        # Check for duplicate properties definition
        if prop_type == "object":
            props = [prop["name"] for prop in normalized["properties"]]
            if len(props) > len(set(props)):
                raise ValidationError("Duplicate properties")
        return normalized
    elif st not in ["integer", "float", "string", "object", "array", "boolean", "schema"]:
        raise ValidationError("Unknown type: %s" % st)
    raise ValidationError("Invalid %s: %s" % (st, datum,))

META_SCHEMA = {
    "type": "object",
    "properties": [
        {
            "name": "type",
            "required": True,
            "schema": {"type": "string"}
        },
        {
            "name": "items",
            "required": False,
            "schema": {"type": "schema"}
        },
        {
            "name": "properties",
            "required": False,
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": [
                        {
                            "name": "name",
                            "required": True,
                            "schema": {"type": "string"}
                        },
                        {
                            "name": "required",
                            "required": True,
                            "schema": {"type": "boolean"}
                        },
                        {
                            "name": "schema",
                            "required": True,
                            "schema": {"type": "schema"}
                        }
                    ]
                }
            }
        }
    ]
}
