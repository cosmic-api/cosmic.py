import sys
import json

from cosmic.exceptions import ValidationError, UnicodeDecodeValidationError, SpecError


class Model(object):
    def __init__(self, data=None):
        self.data = data

    def serialize(self):
        return serialize_json(self.data)

    @classmethod
    def validate(cls, datum):
        return

    @classmethod
    def from_json(cls, datum):
        # Normalize against model schema
        schema = cls.get_schema()
        if schema:
            datum = schema.normalize(datum)
        # Validate against model's custom validation function
        cls.validate(datum)
        # Instantiate
        return cls(datum)

    @classmethod
    def get_schema_cls(cls):
        if hasattr(cls, "schema_cls"):
            return cls.schema_cls
        return Schema

    @classmethod
    def get_schema(cls):
        if hasattr(cls, "schema"):
            return cls.get_schema_cls().from_json(cls.schema)
        return None


class ObjectModel(Model):
    properties = []

    def __getattr__(self, key):
        for prop in self.properties:
            if prop["name"] == key:
                return self.data.get(key, None)
        raise AttributeError()

    def __setattr__(self, key, value):
        for prop in self.properties:
            if prop["name"] == key:
                self.data[key] = value
                return
        super(ObjectModel, self).__setattr__(key, value)

    def serialize(self):
        ret = {}
        for key, val in self.data.items():
            if val != None:
                ret[key] = val
        return serialize_json(ret)

    @classmethod
    def get_schema(cls):
        return cls.get_schema_cls().from_json({
            "type": "object",
            "properties": cls.properties
        })


class JSONData(Model):
    name = u"core.JSON"

    def __repr__(self):
        contents = json.dumps(self.data)
        if len(contents) > 60:
            contents = contents[:56] + " ..."
        return "<JSONData %s>" % contents

    @classmethod
    def from_string(cls, s):
        if s == "":
            return None
        return cls.from_json(json.loads(s))

    @classmethod
    def validate(cls, datum):
        # Hack to make sure we don't end up with non-unicode strings in
        # normalized data
        if type(datum) == str:
            StringNormalizer().normalize(datum)
        elif type(datum) == list:
            for item in datum:
                cls.validate(item)
        elif type(datum) == dict:
            for value in datum.values():
                cls.validate(value)


class Normalizer(Model):

    @classmethod
    def validate(cls, datum):
        if datum["type"] != cls.match_type:
            raise ValidationError("%s expects type=%s" % (cls.__name__, cls.match_type,))


class SimpleNormalizer(Normalizer):

    def __init__(self, data=None):
        # Allow instantiating with no data for convenience's sake
        if data != None:
            self.data = data
        else:
            self.data = {u"type": self.match_type}

    @classmethod
    def get_schema(cls):
        return ObjectNormalizer({
            "type": "object",
            "properties": [
                {
                    "name": "type",
                    "required": True,
                    "schema": StringNormalizer()
                }
            ]
        })


class ModelNormalizer(SimpleNormalizer):

    def serialize(self):
        return {u"type": self.data.name}

    def normalize(self, datum):
        return self.data.from_json(datum)

    @classmethod
    def from_json(cls, datum):
        # Run the schema normalization
        datum = cls.get_schema().normalize(datum)
        # Find model
        t = datum['type']
        if t == "core.JSON":
            model = JSONData
        elif t == "core.Schema":
            model = cls.get_schema_cls()
        elif '.' in t:
            model = cls.get_schema_cls().fetch_model(t)
        else:
            raise ValidationError("Unknown model", t)
        # Instantiate
        return cls(model)



class IntegerNormalizer(SimpleNormalizer):
    match_type = u"integer"

    def normalize(self, datum):
        if type(datum) == int:
            return datum
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer", datum)


class FloatNormalizer(SimpleNormalizer):
    match_type = u"float"

    def normalize(self, datum):
        if type(datum) == float:
            return datum
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float", datum)


class StringNormalizer(SimpleNormalizer):
    match_type = u"string"

    def normalize(self, datum):
        if type(datum) == unicode:
            return datum
        if type(datum) == str:
            try:
                return datum.decode('utf_8')
            except UnicodeDecodeError as inst:
                raise UnicodeDecodeValidationError(unicode(inst))
        raise ValidationError("Invalid string", datum)


class BooleanNormalizer(SimpleNormalizer):
    match_type = u"boolean"

    def normalize(self, datum):
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean", datum)


class ArrayNormalizer(SimpleNormalizer):
    match_type = u"array"

    @classmethod
    def get_schema(cls):
        return ObjectNormalizer({
            "properties": [
                {
                    "name": "type",
                    "required": True,
                    "schema": StringNormalizer()
                },
                {
                    "name": "items",
                    "required": True,
                    "schema": ModelNormalizer(cls.get_schema_cls())
                }
            ]
        })

    def normalize(self, datum):
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(self.data['items'].normalize(item))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid array", datum)


class ObjectNormalizer(SimpleNormalizer):
    match_type = u"object"

    @classmethod
    def get_schema(cls):
        return ObjectNormalizer({
            "properties": [
                {
                    "name": "type",
                    "required": True,
                    "schema": StringNormalizer()
                },
                {
                    "name": "properties",
                    "required": True,
                    "schema": ArrayNormalizer({
                        "items": ObjectNormalizer({
                            "properties": [
                                {
                                    "name": "name",
                                    "required": True,
                                    "schema": StringNormalizer()
                                },
                                {
                                    "name": "required",
                                    "required": True,
                                    "schema": BooleanNormalizer()
                                },
                                {
                                    "name": "schema",
                                    "required": True,
                                    "schema": ModelNormalizer(cls.get_schema_cls())
                                }
                            ]
                        })
                    })
                }
            ]
        })

    @classmethod
    def validate(cls, datum):
        super(ObjectNormalizer, cls).validate(datum)
        # Additional validation to check for duplicate properties
        props = [prop["name"] for prop in datum['properties']]
        if len(props) > len(set(props)):
            raise ValidationError("Duplicate properties")

    def normalize(self, datum):
        properties = self.data['properties']
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
                raise ValidationError("Missing properties", list(missing))
            extra = set(datum.keys()) - set(required.keys() + optional.keys())
            if extra:
                raise ValidationError("Unexpected properties", list(extra))
            for prop, schema in optional.items() + required.items():
                if prop in datum.keys():
                    try:
                        ret[prop] = schema.normalize(datum[prop])
                    except ValidationError as e:
                        e.stack.append(prop)
                        raise
            return ret
        raise ValidationError("Invalid object", datum)


class Schema(Model):
    name = u"core.Schema"

    @classmethod
    def fetch_model(cls, full_name):
        raise ValidationError("The schema you are validating refers to a model (%s), but fetch_model has not been implemented" % full_name)

    @classmethod
    def from_json(cls, datum):
        if type(datum) != dict or "type" not in datum.keys():
            raise ValidationError("Invalid schema", datum)
        st = datum["type"]
        # Model?
        if '.' in st:
            class s(ModelNormalizer):
                schema_cls = cls
            s.__name__ = ModelNormalizer.__name__
            return s.from_json(datum)
        # Simple type?
        else:
            simple = [
                IntegerNormalizer,
                FloatNormalizer,
                StringNormalizer,
                BooleanNormalizer,
                ArrayNormalizer,
                ObjectNormalizer
            ]
            for simple_cls in simple:
                if st == simple_cls.match_type:
                    class s(simple_cls):
                        schema_cls = cls
                    s.__name__ = simple_cls.__name__
                    return s.from_json(datum)
            raise ValidationError("Unknown type", st)


def serialize_json(datum):
    if isinstance(datum, Model):
        return datum.serialize()
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

