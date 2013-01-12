import sys

from apio.exceptions import ValidationError, SpecError



class WildcardSchema(object):
    def normalize(self, datum):
        return datum

class IntegerSchema(object):
    def normalize(self, datum):
        if type(datum) == int:
            return datum
        # A float in place of an int is okay, as long as its
        # fractional part is 0
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer: %s" % (datum,))

class FloatSchema(object):
    def normalize(self, datum):
        if type(datum) == float:
            return datum
        # An int in place of a float is always okay, just cast it for
        # normalization's sake
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float: %s" % (datum,))

class StringSchema(object):
    def normalize(self, datum):
        if type(datum) == unicode:
            return datum
        # Cast to unicode
        if type(datum) == str:
            return unicode(datum)
        raise ValidationError("Invalid string: %s" % (datum,))

class BooleanSchema(object):
    def normalize(self, datum):
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean: %s" % (datum,))

class ArraySchema(object):
    def __init__(self, item_schema):
        self.item_schema = item_schema
    def normalize(self, datum):
        if type(datum) == list:
            return [self.item_schema.normalize(item) for item in datum]
        raise ValidationError("Invalid array: %s" % (datum,))

class ObjectSchema(object):
    def __init__(self, properties):
        self.properties = properties
    def normalize(self, datum):
        if type(datum) == dict:
            ret = {}
            required = {}
            optional = {}
            for prop in self.properties:
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
                    ret[prop] = schema.normalize(datum[prop])
            return ret
        raise ValidationError("Invalid object: %s" % (datum,))


class Model(object):
    schema = {"type": "any"}
    def __init__(self, json_data):
        model_schema = SchemaSchema().normalize(self.schema)
        self.data = model_schema.normalize(json_data)
        self.validate()
    def validate(self):
        pass


class ModelSchema(object):
    def __init__(self, model_cls):
        self.model_cls = model_cls
    def normalize(self, datum):
        return self.model_cls(datum)


class SchemaSchema(object):
    def normalize(self, datum):
        # First make sure it's an object
        datum = ObjectSchema([
            {
                "name": "type",
                "required": True,
                "schema": StringSchema()
            },
            {
                "name": "items",
                "required": False,
                "schema": SchemaSchema()
            },
            {
                "name": "properties",
                "required": False,
                "schema": ArraySchema(ModelSchema(PropertyModel))
            }
        ]).normalize(datum)
        st = datum["type"]
        # Then make sure the attributes are right
        if ((st == "array" and 'items' not in datum.keys()) or
            (st == "object" and 'properties' not in datum.keys()) or
            (st not in ["array", "object"] and len(datum) > 1) or
            (len(datum) == 3)):
            raise ValidationError("Invalid schema: %s" % datum)
        # Just the type?
        if st == "any":
            return WildcardSchema()
        if st == "integer":
            return IntegerSchema()
        if st == "float":
            return FloatSchema()
        if st == "string":
            return StringSchema()
        if st == "boolean":
            return BooleanSchema()
        if st == "schema":
            return SchemaSchema()
        if '.' in st:
            api_name, model_name = st.split('.', 1)
            try:
                api = sys.modules['apio.index.' + api_name]
            except KeyError:
                raise ValidationError("Unknown API: %s" % api_name)
            try:
                model_cls = getattr(api.models, model_name)
            except SpecError:
                raise ValidationError("Unknown model for %s API: %s" % (api_name, model_name))
            return ModelSchema(model_cls)
        if st == "array":
            return ArraySchema(datum['items'])
        if st == "object":
            keys = [prop.data["name"] for prop in datum["properties"]]
            if len(set(keys)) < len(keys):
                raise ValidationError("Duplicate properties in schema: %s" % datum)
            props = [prop.data for prop in datum["properties"]]
            return ObjectSchema(props)
        # None of the above?
        raise ValidationError("Unknown type: %s" % st)


class PropertyModel(object):
    schema = ObjectSchema[
        {
            "name": "name",
            "required": True,
            "schema": StringSchema()
        },
        {
            "name": "required",
            "required": True,
            "schema": BooleanSchema()
        },
        {
            "name": "schema",
            "required": True,
            "schema": ModelSchema(SchemaModel())
        }
    ])

class SchemaModel(object):
    schema = ObjectSchema([
        {
            "name": "type",
            "required": True,
            "schema": StringSchema()
        },
        {
            "name": "items",
            "required": False,
            "schema": SchemaSchema()
        },
        {
            "name": "properties",
            "required": False,
            "schema": ArraySchema(ModelSchema(PropertyModel))
        }
    ])

