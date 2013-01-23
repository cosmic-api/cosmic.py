from __future__ import unicode_literals

import sys

from apio.exceptions import ValidationError, UnicodeDecodeValidationError, SpecError


class Model(object):
    schema = {"type": "any"}
    def __init__(self, data):
        schema = SchemaModel.normalize(self.schema)
        self.data = schema.normalize(data)
        self.validate()
    def validate(self):
        pass
    @classmethod
    def normalize(cls, datum):
        return cls(datum)

class BaseModel(object):
    def __init__(self, data):
        self.data = data
    @classmethod
    def normalize(cls, datum):
        return cls(datum)

class JSONModel(BaseModel):
    def serialize(self):
        return self.data
    @classmethod
    def serialize(cls):
        return {"type": "any"}
    @classmethod
    def from_string(cls, s):
        if s == "":
            return None
        return cls(json.loads(s))
    @classmethod
    def normalize(cls, datum):
        # Hack to make sure we don't end up with non-unicode strings in
        # normalized data
        if type(datum) == str:
            return cls(StringModel.normalize(datum))
        if type(datum) == list:
            return cls([JSONModel.normalize(item).data for item in datum])
        if type(datum) == dict:
            ret = {}
            for key, value in datum.items():
                ret[key] = JSONModel.normalize(value).data
            return cls(ret)
        return cls(datum)

class IntegerModel(BaseModel):
    @classmethod
    def serialize(cls):
        return {"type": "integer"}
    @classmethod
    def normalize(cls, datum):
        """If *datum* is an integer, return it; if it is a float with a 0
        for its fractional part, return the integer part as an
        integer. Otherwise, raise a
        :exc:`~apio.exceptions.ValidationError`.
        """
        if type(datum) == int:
            return datum
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer", datum)

class FloatModel(BaseModel):
    @classmethod
    def serialize(cls):
        return {"type": "float"}
    @classmethod
    def normalize(cls, datum):
        """If *datum* is a float, return it; if it is an integer, cast it
        to a float and return it. Otherwise, raise a
        :exc:`~apio.exceptions.ValidationError`.
        """
        if type(datum) == float:
            return datum
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float", datum)

class StringModel(BaseModel):
    @classmethod
    def serialize(cls):
        return {"type": "string"}
    @classmethod
    def normalize(cls, datum):
        """If *datum* is a unicode string, return it. If it is a string,
        decode it as UTF-8 and return the result. Otherwise, raise a
        :exc:`~apio.exceptions.ValidationError`. Unicode errors are dealt
        with strictly by raising
        :exc:`~apio.exceptions.UnicodeDecodeValidationError`, a subclass
        of the above.
        """
        if type(datum) == unicode:
            return datum
        if type(datum) == str:
            try:
                return datum.decode('utf_8')
            except UnicodeDecodeError as inst:
                raise UnicodeDecodeValidationError(unicode(inst))
        raise ValidationError("Invalid string", datum)

class BooleanModel(BaseModel):
    @classmethod
    def serialize(cls):
        return {"type": "boolean"}
    @classmethod
    def normalize(cls, datum):
        """If *datum* is a boolean, return it. Otherwise, raise a
        :exc:`~apio.exceptions.ValidationError`.
        """
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean", datum)

class ArraySchemaModel(BaseModel):
    def serialize(self):
        return {
            "type": "array",
            "items": self.data.serialize()
        }
    def normalize(self, datum):
        """If *datum* is a list, construct a new list by running the
        *items* normalization function on each element of *datum*. This
        normalization function may raise
        :exc:`~apio.exceptions.ValidationError`. If *datum* is not a list,
        :exc:`~apio.exceptions.ValidationError` will be raised.

        .. code::

            >>> normalize_array([1.0, 2, 3.0], normalize_integer)
            [1, 2, 3]

        """
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(self.data.normalize(item))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid array", datum)

class ObjectSchemaModel(BaseModel):
    def serialize(self):
        props = []
        for prop in self.data:
            props.append({
                "name": prop["name"],
                "required": prop["required"],
                "schema": prop["schema"].serialize()
            })
        return {
            "type": "object",
            "properties": props
        }
    def normalize(self, datum):
        """If *datum* is a dict, normalize it against *properties* and
        return the resulting dict. Otherwise raise a
        :exc:`~apio.exceptions.ValidationError`.

        *properties* must be a list of dicts, where each dict has three
        attributes: *name*, *required* and *schema*. *name* is a string
        representing the property name, *required* is a boolean specifying
        whether the *datum* needs to contain this property in order to
        pass validation and *schema* is a normalization function.

        .. code::

            >>> normalize_object({"spicy": True}, [{
            ...    "name": "spicy",
            ...    "required": True,
            ...    "schema": normalize_boolean
            ... }])
            {"spicy": True}

        A :exc:`~apio.exceptions.ValidationError` will be raised if:

        1. *datum* is missing a required property
        2. *datum* has a property not declared in *properties*.
        3. One of the properties of *datum* does not pass validation as defined
           by the corresponding *schema* value.

        """
        properties = self.data
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

class SchemaModel(BaseModel):
    @classmethod
    def serialize(cls):
        return {"type": "schema"}
    @classmethod
    def normalize(cls, datum):
        """Given a JSON representation of a schema, return a function that
        will normalize data against that schema.

        For primitive types, it returns one of the simple normalization
        functions defined in this module::

            >>> normalizer = normalize_schema({"type": "integer"})
            >>> normalizer(1.0)
            1
            >>> normalizer == normalize_integer
            True

        For array or object types, it will build a custom function by
        wrapping :func:`~apio.models.normalize_array` or
        :func:`~apio.models.normalize_object`. These can be nested as deep
        as you want, :func:`~apio.models.normalize_schema` will recurse::

            >>> normalizer = normalize_schema({
            ...     "type": "array",
            ...     "schema": {"type": "float"}
            ... })
            >>> normalizer([1, 2.2, 3])
            [1.0, 2.2, 3.0]

        """
        if hasattr(datum, "serialize"):
            return datum
        datum = ObjectSchemaModel([
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
                "schema": ArraySchemaModel(
                    ObjectSchemaModel([
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
                    ])
                )
            }
        ]).normalize(datum)
        st = datum["type"]
        # Then make sure the attributes are right
        if ((st == "array" and 'items' not in datum.keys()) or
            (st == "object" and 'properties' not in datum.keys()) or
            (st not in ["array", "object"] and len(datum) > 1) or
            (len(datum) == 3)):
            raise ValidationError("Invalid schema", datum)
        if st == "object":
            keys = [prop["name"] for prop in datum["properties"]]
            if len(set(keys)) < len(keys):
                raise ValidationError("Duplicate properties in schema", datum)
        # Just the type?
        if st == "any":
            return JSONModel
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
                raise ValidationError("Unknown API", api_name)
            try:
                return getattr(api.models, model_name)
            except SpecError:
                raise ValidationError("Unknown model for %s API" % api_name, model_name)
        if st == "array":
            return ArraySchemaModel(datum["items"])
        if st == "object":
            return ObjectSchemaModel(datum["properties"])
        raise ValidationError("Unknown type", st)

def serialize_json(datum):
    if hasattr(datum, "serialize"):
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

