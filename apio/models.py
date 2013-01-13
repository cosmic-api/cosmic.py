import sys

from apio.exceptions import ValidationError, SpecError


class BaseModel(object):
    def __init__(self, datum):
        self.data = datum
    @classmethod
    def normalize(cls, datum):
        return cls(datum)

class WildcardModel(BaseModel):
    @classmethod
    def normalize(cls, datum):
        return datum

class IntegerModel(BaseModel):
    @classmethod
    def normalize(cls, datum):
        if type(datum) == int:
            return datum
        # A float in place of an int is okay, as long as its
        # fractional part is 0
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer: %s" % (datum,))

class FloatModel(BaseModel):
    @classmethod
    def normalize(cls, datum):
        if type(datum) == float:
            return datum
        # An int in place of a float is always okay, just cast it for
        # normalization's sake
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float: %s" % (datum,))

class StringModel(BaseModel):
    @classmethod
    def normalize(cls, datum):
        if type(datum) == unicode:
            return datum
        # Cast to unicode
        if type(datum) == str:
            return unicode(datum)
        raise ValidationError("Invalid string: %s" % (datum,))

class BooleanModel(BaseModel):
    @classmethod
    def normalize(cls, datum):
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean: %s" % (datum,))

class ArrayModel(BaseModel):
    items = WildcardModel
    @classmethod
    def normalize(cls, datum):
        if type(datum) == list:
            return [cls.items.normalize(item) for item in datum]
        raise ValidationError("Invalid array: %s" % (datum,))

class ObjectModel(BaseModel):
    properties = []
    @classmethod
    def normalize(cls, datum):
        if type(datum) == dict:
            ret = {}
            required = {}
            optional = {}
            for prop in cls.properties:
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


class SchemaModel(ObjectModel):
    @classmethod
    def normalize(cls, datum):
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
            return WildcardModel
        if st == "integer":
            return IntegerModel
        if st == "float":
            return FloatModel
        if st == "string":
            return StringModel
        if st == "boolean":
            return BooleanModel
        if st == "schema":
            return SchemaModel
        if '.' in st:
            api_name, model_name = st.split('.', 1)
            try:
                api = sys.modules['apio.index.' + api_name]
            except KeyError:
                raise ValidationError("Unknown API: %s" % api_name)
            try:
                return getattr(api.models, model_name)
            except SpecError:
                raise ValidationError("Unknown model for %s API: %s" % (api_name, model_name))
        if st == "array":
            class CustomArrayModel(ArrayModel):
                items = SchemaModel.normalize(datum["items"])
            return CustomArrayModel
        if st == "object":
            class CustomObjectModel(ObjectModel):
                properties = ArrayOfPropertiesModel.normalize(datum["properties"])
            return CustomObjectModel
        raise ValidationError("Unknown type: %s" % st)

class ArrayOfPropertiesModel(ArrayModel):
    class items(ObjectModel):
        properties = [
            {
                "name": "name",
                "required": True,
                "schema": StringModel
            },
            {
                "name": "required",
                "required": True,
                "schema": BooleanModel
            },
            {
                "name": "schema",
                "required": True,
                "schema": SchemaModel
            }
        ]

SchemaModel.properties = [
    {
        "name": "type",
        "required": True,
        "schema": StringModel
    },
    {
        "name": "items",
        "required": False,
        "schema": SchemaModel
    },
    {
        "name": "properties",
        "required": False,
        "schema": ArrayOfPropertiesModel
    }
]

