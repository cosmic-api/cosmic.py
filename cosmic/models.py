import sys
import json
import base64

from cosmic.exceptions import ValidationError, UnicodeDecodeValidationError, SpecError




class Model(object):

    def __init__(self, data, **kwargs):
        self.data = data
        for key, value in kwargs.items():
            self.__dict__[key] = value

    def serialize(self):
        # Serialize against model schema
        schema = self.get_schema()
        if schema:
            return schema.serialize_data(self.data)
        return self.data

    @classmethod
    def normalize(cls, datum, fetcher=None):
        # Normalize against model schema
        schema = cls.get_schema()
        if schema:
            datum = schema.normalize_data(datum, fetcher=fetcher)
        # Validate against model's custom validation function
        cls.validate(datum)
        # Instantiate
        return cls(datum)

    @classmethod
    def validate(cls, datum):
        pass

    @classmethod
    def get_schema(cls):
        if hasattr(cls, "schema"):
            return cls.schema
        return None



class Schema(Model):

    def __init__(self, data=None, **kwargs):
        # It is okay to omit type in the constructor, the Schema
        # will know its type from the match_type attibute
        if data == None:
            data = {u"type": self.match_type}
        super(Schema, self).__init__(data, **kwargs)
        # Everything except for the type becomes an option
        self.opts = self.data.copy()
        self.opts.pop("type", None)

    @classmethod
    def validate(cls, datum):
        if datum["type"] != cls.match_type:
            raise ValidationError("%s expects type=%s" % (cls, cls.match_type,))

    def normalize_data(self, datum, fetcher=None):
        if self.opts:
            return self.model_cls.normalize(datum, self.opts, fetcher=fetcher)
        else:
            return self.model_cls.normalize(datum, fetcher=fetcher)

    def serialize_data(self, datum):
        if self.opts:
            return self.model_cls.serialize(datum, self.opts)
        else:
            return self.model_cls.serialize(datum)

    @classmethod
    def normalize(cls, datum, fetcher=None):

        invalid = ValidationError("Invalid schema", datum)

        # Peek into the object before letting the real models
        # do proper validation
        if type(datum) != dict or "type" not in datum.keys():
            raise invalid
        st = datum["type"]

        # Simple model?
        simple = [
            IntegerSchema,
            FloatSchema,
            StringSchema,
            BinarySchema,
            BooleanSchema,
            ArraySchema,
            ObjectSchema,
            JSONDataSchema,
            SchemaSchema
        ]
        for simple_cls in simple:
            if st == simple_cls.match_type:
                return simple_cls.normalize(datum, fetcher=fetcher)

        # Model?
        if '.' in st:
            if not fetcher:
                raise NotImplementedError()
            m = fetcher(st)
            class normalizer(SimpleSchema):
                model_cls = m
                match_type = st
            return normalizer.normalize(datum, fetcher=fetcher)

        raise ValidationError("Unknown type", st)



class SimpleSchema(Schema):

    # COPY-PASTE
    @classmethod
    def normalize(cls, datum, fetcher=None):
        # Normalize against model schema
        schema = cls.get_schema()
        datum = schema.normalize_data(datum, fetcher=fetcher)
        # Validate against model's custom validation function
        cls.validate(datum)
        # Instantiate
        return cls(datum)

    @classmethod
    def get_schema(cls):
        return ObjectSchema({
            "type": "object",
            "properties": [
                {
                    "name": "type",
                    "required": True,
                    "schema": StringSchema()
                }
            ]
        })

class SchemaSchema(SimpleSchema):
    match_type = "schema"
    model_cls = Schema




class ObjectModel(Model):

    @classmethod
    def normalize(cls, datum, opts, fetcher=None):
        """If *datum* is a dict, normalize it against ``opts['properties']``
        and return the resulting dict. Otherwise raise a
        :exc:`~cosmic.exceptions.ValidationError`.

        ``opts['properties']`` must be a list of dicts, where each dict has
        three attributes: *name*, *required* and *schema*. *name* is a string
        representing the property name, *required* is a boolean specifying
        whether *datum* needs to contain this property in order to pass
        validation and *schema* is an instance of a
        :class:`~cosmic.models.Schema` subclass, such as :class:`IntegerSchema`.

        A :exc:`~cosmic.exceptions.ValidationError` will be raised if:

        1. *datum* is missing a required property
        2. *datum* has a property not declared in *properties*
        3. One of the properties of *datum* does not pass validation as defined
           by the corresponding *schema*

        """
        properties = opts['properties']
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
                        ret[prop] = schema.normalize_data(datum[prop], fetcher=fetcher)
                    except ValidationError as e:
                        e.stack.append(prop)
                        raise
            return ret
        raise ValidationError("Invalid object", datum)

    @classmethod
    def serialize(cls, datum, opts):
        """For each property in ``opts['properties']``, serialize the
        corresponding value in *datum* (if the value exists) against the
        property schema. Return the resulting dict.
        """
        ret = {}
        for prop in opts['properties']:
            name = prop['name']
            if name in datum.keys() and datum[name] != None:
                ret[name] = prop['schema'].serialize_data(datum[name])
        return ret

class ObjectSchema(SimpleSchema):
    model_cls = ObjectModel
    match_type = "object"

    @classmethod
    def get_schema(cls):
        return ObjectSchema({
            "type": "object",
            "properties": [
                {
                    "name": "type",
                    "required": True,
                    "schema": StringSchema()
                },
                {
                    "name": "properties",
                    "required": True,
                    "schema": ArraySchema({
                        "items": ObjectSchema({
                            "properties": [
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
                                    "schema": SchemaSchema()
                                }
                            ]
                        })
                    })
                }
            ]
        })

    @classmethod
    def validate(cls, datum):
        """Raises :exc:`~cosmic.exception.ValidationError` if there are two
        properties with the same name.
        """
        super(ObjectSchema, cls).validate(datum)
        # Additional validation to check for duplicate properties
        props = [prop["name"] for prop in datum['properties']]
        if len(props) > len(set(props)):
            raise ValidationError("Duplicate properties")







class ArrayModel(Model):

    @classmethod
    def normalize(cls, datum, opts, fetcher=None):
        """If *datum* is a list, construct a new list by putting each element
        of *datum* through a schema provided as ``opts['items']``. This schema
        may raise
        :exc:`~cosmic.exceptions.ValidationError`. If *datum* is not a list,
        :exc:`~cosmic.exceptions.ValidationError` will be raised.
        """
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(opts['items'].normalize_data(item, fetcher=fetcher))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid array", datum)

    @classmethod
    def serialize(cls, datum, opts):
        """Serialize each item in the *datum* list using the schema provided
        in ``opts['items']``. Return the resulting list.
        """
        return [opts['items'].serialize_data(item) for item in datum]

class ArraySchema(SimpleSchema):
    model_cls = ArrayModel
    match_type = u"array"

    @classmethod
    def get_schema(cls):
        return ObjectSchema({
            "properties": [
                {
                    "name": "type",
                    "required": True,
                    "schema": StringSchema()
                },
                {
                    "name": "items",
                    "required": True,
                    "schema": SchemaSchema()
                }
            ]
        })





class IntegerModel(Model):

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is an integer, return it; if it is a float with a 0 for
        its fractional part, return the integer part as an int. Otherwise,
        raise a
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

class IntegerSchema(SimpleSchema):
    model_cls = IntegerModel
    match_type = "integer"




class FloatModel(Model):

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is a float, return it; if it is an integer, cast it to a
        float and return it. Otherwise, raise a
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

class FloatSchema(SimpleSchema):
    model_cls = FloatModel
    match_type = "float"




class StringModel(Model):

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is of unicode type, return it. If it is a string, decode
        it as UTF-8 and return the result. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`. Unicode errors are dealt
        with strictly by raising
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

class StringSchema(SimpleSchema):
    model_cls = StringModel
    match_type = "string"





class BinaryModel(Model):

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is a base64-encoded string, decode and return it. If not
        a string, or encoding is wrong, raise
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
        """Encode *datum* in base64."""
        return base64.b64encode(datum)

class BinarySchema(SimpleSchema):
    model_cls = BinaryModel
    match_type = "binary"




class BooleanModel(Model):

    @classmethod
    def normalize(cls, datum, **kwargs):
        """If *datum* is a boolean, return it. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean", datum)

    @classmethod
    def serialize(cls, datum):
        return datum

class BooleanSchema(SimpleSchema):
    model_cls = BooleanModel
    match_type = "boolean"





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

class JSONDataSchema(SimpleSchema):
    model_cls = JSONData
    match_type = "json"



class ClassModel(ObjectModel):

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
    def normalize(cls, datum, fetcher=None):
        datum = cls.get_schema().normalize_data(datum, fetcher=fetcher)
        cls.validate(datum)
        return cls(datum)

    def serialize(self):
        return self.get_schema().serialize_data(self.data)

    @classmethod
    def get_schema(cls):
        return ObjectSchema({
            "type": "object",
            "properties": cls.properties
        })

