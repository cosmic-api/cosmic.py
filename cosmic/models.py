import sys
import json
import base64

from cosmic.exceptions import ValidationError, UnicodeDecodeValidationError, SpecError


class Model(object):

    def __init__(self, data, **kwargs):
        self.data = data
        for key, value in kwargs.items():
            self.__dict__[key] = value

    def serialize(self, data=None):
        # Serialize against model schema
        schema = self.get_schema()
        if schema:
            return schema.serialize_data(self.data)
        return self.data

    @classmethod
    def normalize(cls, datum, data=None):
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
    def get_schema(cls):
        if hasattr(cls, "schema"):
            return cls.schema
        return None



class N(Model):

    def __init__(self, data=None):
        if data != None:
            self.data = data
        else:
            self.data = {u"type": self.match_type}
        # Everything except for the type becomes an option
        self.opts = self.data.copy()
        self.opts.pop("type", None)

    @classmethod
    def fetch_model(cls, model_name):
        raise NotImplementedError("fetch_model not implemented")

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
            raise ValidationError("%s expects type=%s" % (cls, cls.match_type,))

    def normalize_data(self, datum):
        if self.opts:
            return self.model_cls.normalize(datum, self.opts)
        else:
            return self.model_cls.normalize(datum)

    def serialize_data(self, datum):
        if self.opts:
            return self.model_cls.serialize(datum, self.opts)
        else:
            return self.model_cls.serialize(datum)

    @classmethod
    def normalize(cls, datum):

        invalid = ValidationError("Invalid schema", datum)

        # Get type or fail
        if type(datum) != dict or "type" not in datum.keys():
            raise invalid
        st = datum["type"]

        # Special case, don't normalize, just instantiate
        if st == "schema":
            if len(datum) > 1:
                raise invalid
            return cls.N()

        # Simple type?
        simple = [
            IntegerModel,
            FloatModel,
            StringModel,
            BinaryModel,
            BooleanModel,
            ArrayModel,
            ObjectModel,
            JSONData
        ]
        for model_cls in simple:
            if st == model_cls.N.match_type:
                class m(model_cls):
                    class N(model_cls.N, cls):
                        pass
                m.__name__ = model_cls.__name__
                m.N.model_cls = m
                inst = m.N.normalize(datum)
                return inst

        # Model?
        if '.' in st:
            model_cls = cls.fetch_model(st)
            return model_cls.N.normalize(datum)

        raise ValidationError("Unknown type", st)

class NN(N):
    match_type = "schema"
    model_cls = N

N.N = NN


class SN(N):

    # COPY-PASTE
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
    def get_schema(cls):
        return ObjectModel.N({
            "type": "object",
            "properties": [
                {
                    "name": "type",
                    "required": True,
                    "schema": StringModel.N()
                }
            ]
        })



class ObjectModel(Model):

    class N(SN):
        match_type = "object"

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
            return ObjectModel.N({
                "type": "object",
                "properties": [
                    {
                        "name": "type",
                        "required": True,
                        "schema": StringModel.N()
                    },
                    {
                        "name": "properties",
                        "required": True,
                        "schema": ArrayModel.N({
                            "items": ObjectModel.N({
                                "properties": [
                                    {
                                        "name": "name",
                                        "required": True,
                                        "schema": StringModel.N()
                                    },
                                    {
                                        "name": "required",
                                        "required": True,
                                        "schema": BooleanModel.N()
                                    },
                                    {
                                        "name": "schema",
                                        "required": True,
                                        "schema": cls.N()
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
            super(N, cls).validate(datum)
            # Additional validation to check for duplicate properties
            props = [prop["name"] for prop in datum['properties']]
            if len(props) > len(set(props)):
                raise ValidationError("Duplicate properties")


    @classmethod
    def normalize(cls, datum, opts):
        """If *datum* is a dict, normalize it against *properties* and return
        the resulting dict. Otherwise raise a
        :exc:`~cosmic.exceptions.ValidationError`.

        *properties* must be a list of dicts, where each dict has three
        attributes: *name*, *required* and *schema*. *name* is a string
        representing the property name, *required* is a boolean specifying
        whether the *datum* needs to contain this property in order to pass
        validation and *schema* is a normalization function.

        A :exc:`~cosmic.exceptions.ValidationError` will be raised if:

        1. *datum* is missing a required property
        2. *datum* has a property not declared in *properties*.
        3. One of the properties of *datum* does not pass validation as defined
           by the corresponding *schema* value.

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
                        ret[prop] = schema.normalize_data(datum[prop])
                    except ValidationError as e:
                        e.stack.append(prop)
                        raise
            return ret
        raise ValidationError("Invalid object", datum)

    @classmethod
    def serialize(cls, datum, opts):
        ret = {}
        for prop in opts['properties']:
            name = prop['name']
            if name in datum.keys() and datum[name] != None:
                ret[name] = prop['schema'].serialize_data(datum[name])
        return ret

ObjectModel.N.model_cls = ObjectModel


class ArrayModel(Model):

    class N(SN):
        match_type = u"array"

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
            return ObjectModel.N({
                "properties": [
                    {
                        "name": "type",
                        "required": True,
                        "schema": StringModel.N()
                    },
                    {
                        "name": "items",
                        "required": True,
                        "schema": cls.N()
                    }
                ]
            })

    @classmethod
    def normalize(cls, datum, opts):
        """If *datum* is a list, construct a new list by putting each element of
        *datum* through the normalizer provided as *items*. This normalizer may
        raise
        :exc:`~cosmic.exceptions.ValidationError`. If *datum* is not a list,
        :exc:`~cosmic.exceptions.ValidationError` will be raised.
        """
        items = opts['items']
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(items.normalize_data(item))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid array", datum)

    @classmethod
    def serialize(cls, datum, opts):
        return [opts['items'].serialize_data(item) for item in datum]

ArrayModel.N.model_cls = ArrayModel


class IntegerModel(Model):

    class N(SN):
        match_type = "integer"

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

IntegerModel.N.model_cls = IntegerModel


class FloatModel(Model):

    class N(SN):
        match_type = "float"

    @classmethod
    def normalize(cls, datum):
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

FloatModel.N.model_cls = FloatModel



class StringModel(Model):

    class N(SN):
        match_type = "string"

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

StringModel.N.model_cls = StringModel



class BinaryModel(Model):

    class N(SN):
        match_type = "binary"

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

BinaryModel.N.model_cls = BinaryModel




class BooleanModel(Model):

    class N(SN):
        match_type = "boolean"

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

BooleanModel.N.model_cls = BooleanModel





class JSONData(Model):

    class N(SN):
        match_type = "json"

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
            StringModel.N().normalize_data(datum)
        elif type(datum) == list:
            for item in datum:
                cls.validate(item)
        elif type(datum) == dict:
            for value in datum.values():
                cls.validate(value)

JSONData.N.model_cls = JSONData



class ClassModel(ObjectModel):

    class N(ObjectModel.N):
        pass

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
    def normalize(cls, datum):
        datum = cls.get_schema().normalize_data(datum)
        cls.validate(datum)
        return cls(datum)

    def serialize(self):
        return self.get_schema().serialize_data(self.data)

    @classmethod
    def get_schema(cls):
        return ObjectModel.N({
            "type": "object",
            "properties": cls.properties
        })

ClassModel.N.model_cls = ClassModel
