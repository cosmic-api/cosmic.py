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
        return datum

    @classmethod
    def from_json(cls, datum):
        # Normalize against model schema
        schema = cls.get_schema()
        if schema:
            datum = schema.normalize(datum)
        # Validate against model's custom validation function
        datum = cls.validate(datum)
        # Instantiate
        return cls(datum)

    @classmethod
    def get_schema(cls):
        if hasattr(cls, "schema"):
            return Schema.make_normalizer().normalize(cls.schema)
        return None

    @classmethod
    def make_normalizer(cls, datum=None):
        normalizer = ModelNormalizer(datum)
        normalizer.model_cls = cls
        return normalizer


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
        return Schema.make_normalizer().normalize({
            "type": "object",
            "properties": cls.properties
        })

class JSONData(Model):
    name = "core.JSON"

    def __repr__(self):
        contents = json.dumps(self.data)
        if len(contents) > 60:
            contents = contents[:56] + " ..."
        return "<JSONData %s>" % contents

    @classmethod
    def from_string(cls, s):
        if s == "":
            return None
        return cls.make_normalizer().normalize(json.loads(s))

    @classmethod
    def validate(cls, datum):
        # Hack to make sure we don't end up with non-unicode strings in
        # normalized data
        if type(datum) == str:
            return StringNormalizer().normalize(datum)
        if type(datum) == list:
            return [cls.validate(item) for item in datum]
        if type(datum) == dict:
            ret = {}
            for key, value in datum.items():
                ret[key] = cls.validate(value)
            return ret
        return datum


class Normalizer(ObjectModel):
    pass

class SimpleNormalizer(Normalizer):

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

    @classmethod
    def validate(cls, datum):
        if datum["type"] != cls.match_type:
            raise ValidationError("%s expects type=%s" % (cls.__name__, cls.match_type,))
        return datum

    def serialize(self):
        return {u"type": self.match_type}


class ModelNormalizer(Normalizer):

    def serialize(self):
        return {u"type": self.model_cls.name}

    def normalize(self, datum):
        return self.model_cls.from_json(datum)


class IntegerNormalizer(SimpleNormalizer):
    match_type = "integer"

    def normalize(self, datum):
        if type(datum) == int:
            return datum
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer", datum)


class FloatNormalizer(SimpleNormalizer):
    match_type = "float"

    def normalize(self, datum):
        if type(datum) == float:
            return datum
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float", datum)


class StringNormalizer(SimpleNormalizer):
    match_type = "string"

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
    match_type = "boolean"

    def normalize(self, datum):
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean", datum)


class ArrayNormalizer(SimpleNormalizer):
    match_type = "array"

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
                    "schema": Schema.make_normalizer()
                }
            ]
        })

    def serialize(self):
        return {
            u"type": u"array",
            u"items": self.data['items'].serialize()
        }

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
    match_type = "object"

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
                                    "schema": Schema.make_normalizer()
                                }
                            ]
                        })
                    })
                }
            ]
        })

    @classmethod
    def validate(cls, datum):
        # Additional validation to check for duplicate properties
        props = [prop["name"] for prop in datum['properties']]
        if len(props) > len(set(props)):
            raise ValidationError("Duplicate properties")
        return datum

    def serialize(self):
        props = []
        for prop in self.data['properties']:
            props.append({
                u"name": prop["name"],
                u"required": prop["required"],
                u"schema": prop["schema"].serialize()
            })
        return {
            u"type": u"object",
            u"properties": props
        }

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
        # Simple type?
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
                return simple_cls.from_json(datum)
        # Model?
        else:
            if st == "core.JSON":
                return JSONData.make_normalizer(datum)
            elif st == "core.Schema":
                return cls.make_normalizer(datum)
            elif '.' in st:
                return cls.fetch_model(st).make_normalizer(datum)
            else:
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
    if isinstance(datum, Model):
        return serialize_json(datum.data)

