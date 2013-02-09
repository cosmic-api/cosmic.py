import sys
import json
import base64

from cosmic.exceptions import ValidationError, UnicodeDecodeValidationError, SpecError


class Model(object):
    def __init__(self, data=None):
        self.data = data

    def serialize(self):
        # Serialize against model schema
        schema = self.get_schema()
        if schema:
            return schema.serialize_data(self.data)
        return self.data

    @classmethod
    def normalize(cls, datum):
        # Normalize against model schema
        schema = cls.get_schema()
        if schema:
            datum = schema.normalize_data(datum)
        # Validate against model's custom validation function
        cls.validate(datum)
        # Instantiate
        return cls(datum)

    @classmethod
    def validate(cls, datum):
        pass

    @classmethod
    def get_schema_cls(cls):
        if hasattr(cls, "schema_cls"):
            return cls.schema_cls
        return Schema

    @classmethod
    def get_schema(cls):
        if hasattr(cls, "schema"):
            return cls.get_schema_cls().normalize(cls.schema)
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
                if value == None:
                    del self.data[key]
                else:
                    self.data[key] = value
                return
        super(ObjectModel, self).__setattr__(key, value)

    @classmethod
    def get_schema(cls):
        return cls.get_schema_cls().normalize({
            "type": "object",
            "properties": cls.properties
        })


class Normalizer(Model):

    @classmethod
    def validate(cls, datum):
        """Make sure the *type* attribute matches the normalizer
        type.

        Realistically, no one is going to try::

            >>> StringNormalizer.normalize({"type": "integer"})

        But because normalizers are models, validation has to be
        thorough.
        """
        if datum["type"] != cls.match_type:
            raise ValidationError("%s expects type=%s" % (cls.__name__, cls.match_type,))


class SimpleNormalizer(Normalizer):
    """All simple normalizers have the same schema, which they will
    inherit from this class. Because there is, in effect, only one
    legal value they can be instantiated with, the constructor will
    make it optional for the sake of convenience.

    Common schema:

    .. code:: json

        {
            "type": "object",
            "properties": [
                {
                    "name": "type",
                    "required": true,
                    "schema": {"type": "string"}
                }
            ]
        }

    """

    def __init__(self, data=None):
        if data != None:
            self.data = data
        else:
            self.data = {u"type": self.match_type}

    def normalize_data(self, datum):
        return self.model.normalize(datum)

    def serialize_data(self, datum):
        return self.model.serialize(datum)

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



class ObjectMModel(object):

    @classmethod
    def normalize(cls, datum):
        """If *datum* is a dict, normalize it against *properties* and
        return the resulting dict. Otherwise raise a
        :exc:`~cosmic.exceptions.ValidationError`.

        *properties* must be a list of dicts, where each dict has
        three attributes: *name*, *required* and *schema*. *name* is a
        string representing the property name, *required* is a boolean
        specifying whether the *datum* needs to contain this property
        in order to pass validation and *schema* is a normalization
        function.

        A :exc:`~cosmic.exceptions.ValidationError` will be raised if:

        1. *datum* is missing a required property
        2. *datum* has a property not declared in *properties*.
        3. One of the properties of *datum* does not pass validation as defined
           by the corresponding *schema* value.

        """
        properties = cls.properties
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
                        ret[prop] = schema.normalize_data(datum[prop])
                    except ValidationError as e:
                        e.stack.append(prop)
                        raise
            return ret
        raise ValidationError("Invalid object", datum)

    @classmethod
    def serialize(cls, datum):
        ret = {}
        for prop in cls.properties:
            name = prop['name']
            if name in datum.keys() and datum[name] != None:
                ret[name] = prop['schema'].serialize_data(datum[name])
        return ret


class ArrayModel(object):

    @classmethod
    def normalize(cls, datum):
        """If *datum* is a list, construct a new list by putting each
        element of *datum* through the normalizer provided as
        *items*. This normalizer may raise
        :exc:`~cosmic.exceptions.ValidationError`. If *datum* is not a
        list, :exc:`~cosmic.exceptions.ValidationError` will be
        raised.
        """
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(cls.items.normalize_data(item))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid array", datum)

    @classmethod
    def serialize(cls, datum):
        return [cls.items.serialize_data(item) for item in datum]


class IntegerModel(object):

    @classmethod
    def normalize(cls, datum):
        """If *datum* is an integer, return it; if it is a float with
        a 0 for its fractional part, return the integer part as an
        int. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == int:
            return datum
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer", datum)

    @classmethod
    def serialize(cls, datum):
        return datum


class FloatModel(object):

    @classmethod
    def normalize(cls, datum):
        """If *datum* is a float, return it; if it is an integer, cast
        it to a float and return it. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == float:
            return datum
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float", datum)

    @classmethod
    def serialize(cls, datum):
        return datum


class StringModel(object):

    @classmethod
    def normalize(cls, datum):
        """If *datum* is of unicode type, return it. If it is a string, decode
        it as UTF-8 and return the result. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`. Unicode errors are dealt with
        strictly by raising
        :exc:`~cosmic.exceptions.UnicodeDecodeValidationError`, a
        subclass of the above.
        """
        if type(datum) == unicode:
            return datum
        if type(datum) == str:
            try:
                return datum.decode('utf_8')
            except UnicodeDecodeError as inst:
                raise UnicodeDecodeValidationError(unicode(inst))
        raise ValidationError("Invalid string", datum)

    @classmethod
    def serialize(cls, datum):
        return datum


class BinaryModel(object):

    @classmethod
    def normalize(cls, datum):
        """If *datum* is a base64-encoded string, decode and return it. If not a
        string, or encoding is wrong, raise
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) in (str, unicode,):
            try:
                return base64.b64decode(datum)
            except TypeError:
                raise ValidationError("Invalid base64 encoding", datum)
        raise ValidationError("Invalid binary data", datum)

    @classmethod
    def serialize(cls, datum):
        return base64.b64encode(datum)


class BooleanModel(object):

    @classmethod
    def normalize(cls, datum):
        """If *datum* is a boolean, return it. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean", datum)

    @classmethod
    def serialize(cls, datum):
        return datum


class JSONData(Model):

    def serialize(self):
        return self.data

    def __repr__(self):
        contents = json.dumps(self.data)
        if len(contents) > 60:
            contents = contents[:56] + " ..."
        return "<JSONData %s>" % contents

    @classmethod
    def from_string(cls, s):
        if s == "":
            return None
        return cls.normalize(json.loads(s))

    @classmethod
    def validate(cls, datum):
        # Hack to make sure we don't end up with non-unicode strings in
        # normalized data
        if type(datum) == str:
            StringNormalizer().normalize_data(datum)
        elif type(datum) == list:
            for item in datum:
                cls.validate(item)
        elif type(datum) == dict:
            for value in datum.values():
                cls.validate(value)


class Schema(Model):

    @classmethod
    def fetch_model(cls, full_name):
        raise ValidationError("The schema you are validating refers to a model (%s), but fetch_model has not been implemented" % full_name)

    @classmethod
    def get_normalizer(cls):
        class N(SimpleNormalizer):
            match_type = u"schema"
            model = cls
        return N()

    @classmethod
    def normalize(cls, datum):
        if type(datum) != dict or "type" not in datum.keys():
            raise ValidationError("Invalid schema", datum)
        st = datum["type"]
        # Simple type?
        simple = [
            IntegerNormalizer,
            FloatNormalizer,
            StringNormalizer,
            BinaryNormalizer,
            BooleanNormalizer,
            ArrayNormalizer,
            ObjectNormalizer,
            JSONDataNormalizer,
            SchemaNormalizer
        ]
        for simple_cls in simple:
            if st == simple_cls.match_type:
                class s(simple_cls):
                    schema_cls = cls
                s.__name__ = simple_cls.__name__
                return s.normalize(datum)
        # Model?
        if '.' in st:
            model_cls = cls.fetch_model(st)
            class s(SimpleNormalizer):
                match_type = st
                model = model_cls
                def serialize_data(self, datum):
                    return datum.__class__.serialize(datum)
            return s.normalize(datum)
        raise ValidationError("Unknown type", st)

    @classmethod
    def serialize(cls, datum):
        return datum.serialize()


class JSONDataNormalizer(SimpleNormalizer):
    match_type = u"json"
    model = JSONData

class SchemaNormalizer(SimpleNormalizer):
    match_type = u"schema"
    model = Schema

class IntegerNormalizer(SimpleNormalizer):
    match_type = u"integer"
    model = IntegerModel

class FloatNormalizer(SimpleNormalizer):
    match_type = u"float"
    model = FloatModel

class StringNormalizer(SimpleNormalizer):
    match_type = u"string"
    model = StringModel

class BinaryNormalizer(SimpleNormalizer):
    match_type = u"binary"
    model = BinaryModel

class BooleanNormalizer(SimpleNormalizer):
    match_type = u"boolean"
    model = BooleanModel

class ArrayNormalizer(Normalizer):
    match_type = u"array"
    model = ArrayModel

    @classmethod
    def get_schema(cls):
        """Schema is as follows:

        .. code:: json

            {
                "type": "object",
                "properties": [
                    {
                        "name": "type",
                        "required": true,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "items",
                        "required": true,
                        "schema": {"type": "schema"}
                    }
                ]
            }

        """
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
                    "schema": cls.get_schema_cls().get_normalizer()
                }
            ]
        })

    def normalize_data(self, datum):
        class N(ArrayModel):
            items = self.data['items']
        return N.normalize(datum)

    def serialize_data(self, datum):
        class N(ArrayModel):
            items = self.data['items']
        return N.serialize(datum)


class ObjectNormalizer(Normalizer):
    match_type = u"object"
    model = ObjectModel

    @classmethod
    def get_schema(cls):
        """Schema is as follows:

        .. code:: json

            {
                "type": "object",
                "properties": [
                    {
                        "name": "type",
                        "required": true,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "properties",
                        "required": true,
                        "schema": {
                            "items": {
                                "properties": [
                                    {
                                        "name": "name",
                                        "required": true,
                                        "schema": {"type": "string"}
                                    },
                                    {
                                        "name": "required",
                                        "required": true,
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

        """
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
                                    "schema": cls.get_schema_cls().get_normalizer()
                                }
                            ]
                        })
                    })
                }
            ]
        })

    @classmethod
    def validate(cls, datum):
        """Raises :exc:`~cosmic.exception.ValidationError` if there
        are two properties with the same name.
        """
        super(ObjectNormalizer, cls).validate(datum)
        # Additional validation to check for duplicate properties
        props = [prop["name"] for prop in datum['properties']]
        if len(props) > len(set(props)):
            raise ValidationError("Duplicate properties")

    def normalize_data(self, datum):
        class N(ObjectMModel):
            properties = self.data['properties']
        return N.normalize(datum)

    def serialize_data(self, datum):
        class N(ObjectMModel):
            properties = self.data['properties']
        return N.serialize(datum)

