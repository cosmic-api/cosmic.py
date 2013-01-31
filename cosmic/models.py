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
        return cls.make_normalizer().normalize(datum)
    @classmethod
    def get_schema(cls):
        if hasattr(cls, "schema"):
            return Schema.make_normalizer().normalize(cls.schema)
        return None
    @classmethod
    def make_normalizer(cls, *args, **kwargs):
        normalizer = ModelNormalizer(*args, **kwargs)
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

class Normalizer(ObjectModel):
    pass

class ModelNormalizer(Normalizer):

    def serialize(self):
        return {u"type": self.model_cls.name}

    def normalize(self, datum):
        # Normalize against model schema
        schema = self.model_cls.get_schema()
        if schema:
            datum = schema.normalize(datum)
        # Validate against model's custom validation function
        datum = self.model_cls.validate(datum)
        # Instantiate
        return self.model_cls(datum)

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

class IntegerNormalizer(Normalizer):
    def serialize(self):
        return {u"type": u"integer"}
    def normalize(self, datum):
        if type(datum) == int:
            return datum
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer", datum)

class FloatNormalizer(Normalizer):
    def serialize(self):
        return {u"type": u"float"}
    def normalize(self, datum):
        if type(datum) == float:
            return datum
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float", datum)

class StringNormalizer(Normalizer):
    def serialize(self):
        return {u"type": u"string"}
    def normalize(self, datum):
        if type(datum) == unicode:
            return datum
        if type(datum) == str:
            try:
                return datum.decode('utf_8')
            except UnicodeDecodeError as inst:
                raise UnicodeDecodeValidationError(unicode(inst))
        raise ValidationError("Invalid string", datum)

class BooleanNormalizer(Normalizer):
    def serialize(self):
        return {u"type": u"boolean"}
    def normalize(self, datum):
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean", datum)

class ArrayNormalizer(Model):

    @classmethod
    def get_schema(cls):
        return Schema(ObjectNormalizer({
            "properties": [
                {
                    "name": "items",
                    "required": True,
                    "schema": Schema(Schema.make_normalizer())
                }
            ]
        }))

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

class ObjectNormalizer(Model):

    @classmethod
    def get_schema(cls):
        return Schema(ObjectNormalizer({
            "properties": [
                {
                    "name": "properties",
                    "required": True,
                    "schema": Schema(ArrayNormalizer({
                        "items": Schema(ObjectNormalizer({
                            "properties": [
                                {
                                    "name": "name",
                                    "required": True,
                                    "schema": Schema(StringNormalizer())
                                },
                                {
                                    "name": "required",
                                    "required": True,
                                    "schema": Schema(BooleanNormalizer())
                                },
                                {
                                    "name": "schema",
                                    "required": True,
                                    "schema": Schema(Schema.make_normalizer())
                                }
                            ]
                        }))
                    }))
                }
            ]
        }))

    @classmethod
    def validate(cls, datum):
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

    def normalize(self, datum):
        return self.data.normalize(datum)

    def serialize(self):
        return self.data.serialize()

    @classmethod
    def fetch_model(cls, full_name):
        raise ValidationError("The schema you are validating refers to a model (%s), but fetch_model has not been implemented" % full_name)

    @classmethod
    def validate(cls, datum):
        if type(datum) != dict or "type" not in datum.keys():
            raise ValidationError("Invalid schema", datum)
        st = datum["type"]
        # Everything other than type becomes an attribute
        attrs = datum.copy()
        attrs.pop("type")
        simple = {
            "integer": IntegerNormalizer,
            "float": FloatNormalizer,
            "string": StringNormalizer,
            "boolean": BooleanNormalizer,
            "array": ArrayNormalizer,
            "object": ObjectNormalizer
        }
        # Simple type?
        if st in simple.keys():
            return simple[st].from_json(attrs)
        # Model?
        else:
            if st == "core.JSON":
                return JSONData.make_normalizer(**attrs)
            elif st == "core.Schema":
                return cls.make_normalizer(**attrs)
            elif '.' in st:
                return cls.fetch_model(st).make_normalizer(**attrs)
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

