import sys

from apio.exceptions import ValidationError, SpecError


def normalize_wildcard(datum):
    return datum

def normalize_integer(datum):
    if type(datum) == int:
        return datum
    # A float in place of an int is okay, as long as its
    # fractional part is 0
    if type(datum) == float and datum.is_integer():
        return int(datum)
    raise ValidationError("Invalid integer: %s" % (datum,))

def normalize_float(datum):
    if type(datum) == float:
        return datum
    # An int in place of a float is always okay, just cast it for
    # normalization's sake
    if type(datum) == int:
        return float(datum)
    raise ValidationError("Invalid float: %s" % (datum,))

def normalize_string(datum):
    if type(datum) == unicode:
        return datum
    # Cast to unicode
    if type(datum) == str:
        return unicode(datum)
    raise ValidationError("Invalid string: %s" % (datum,))

def normalize_boolean(datum):
    if type(datum) == bool:
        return datum
    raise ValidationError("Invalid boolean: %s" % (datum,))

def normalize_array(datum, items):
    if type(datum) == list:
        return [items(item) for item in datum]
    raise ValidationError("Invalid array: %s" % (datum,))

def normalize_object(datum, properties):
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
            return lambda datum: model(datum)
        except SpecError:
            raise ValidationError("Unknown model for %s API: %s" % (api_name, model_name))
    if st == "array":
        items = datum["items"]
        return lambda datum: normalize_array(datum, items)
    if st == "object":
        properties = datum["properties"]
        return lambda datum: normalize_object(datum, properties)
    raise ValidationError("Unknown type: %s" % st)

class Model(object):
    schema = {"type": "any"}
    def __init__(self, data):
        schema = normalize_schema(self.schema)
        self.data = schema(data)
        self.validate()
    def validate(self):
        pass
