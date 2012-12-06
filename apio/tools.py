import inspect
import json

from apio.exceptions import SpecError, InvalidCallError, ValidationError

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
        "properties": {}
    }
    # Number of non-keyword arguments (required ones)
    numargs = len(args) - (len(defaults) if defaults else 0)

    for i, arg in enumerate(args):
        if i < numargs:
            s = { "type": "any", "required": True }
        else:
            s = { "type": "any" }
        spec["properties"][arg] = s
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
    if detailed["type"] != "object" or "properties" not in detailed.keys():
        return False
    if set(general["properties"].keys()) != set(detailed["properties"].keys()):
        return False
    for attr in general["properties"].keys():
        # Check for required attributes, False by default
        try:
            req_general = general["properties"][attr]["required"]
        except KeyError:
            req_general = False
        try:
            req_detailed = detailed["properties"][attr]["required"]
        except KeyError:
            req_detailed = False
        if req_general != req_detailed:
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
    # Base cases
    types = {
        "int": int,
        "string": unicode,
        "bool": bool,
        "float": float
    }
    if st in types.keys() and dt == types[st]:
        return datum
    # A float in place of an int is okay, as long as its fractional
    # part is 0
    if st == "int" and dt == float and datum.is_integer():
        return int(datum)
    # An int in place of a float is always okay, just cast it for
    # normalization's sake
    if st == "float" and dt == int:
        return float(datum)
    if st == "array" and dt == list:
        return [normalize(schema["items"], item) for item in datum]
    if st == "object" and dt == dict:
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
            ret[prop] = normalize(schema, datum[prop])
        return ret
    # Specify that we want _unicode_ strings, not str
    if st == "string" and dt == str:
        raise ValidationError("Expected unicode string, got %s" % dt)
    raise ValidationError("Expected %s, got %s" % (st, dt,))
