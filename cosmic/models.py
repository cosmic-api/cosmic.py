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
    def normalize(cls, datum):
        return ModelNormalizer(cls).normalize(datum)
    @classmethod
    def get_schema(cls):
        if hasattr(cls, "schema"):
            return cls.schema
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
                if value != None:
                    self.data[key] = value
                elif key in self.data:
                    del self.data[key]
                return
        super(ObjectModel, self).__setattr__(key, value)

    @classmethod
    def get_schema(cls):
        return {
            "type": "object",
            "properties": cls.properties
        }

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
        return ModelNormalizer(cls).normalize(json.loads(s))
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

class Normalizer(object):
    pass

class ModelNormalizer(Normalizer):
    def __init__(self, model_cls):
        self.model_cls = model_cls
    @property
    def validates(self):
        return {u"type": self.model_cls.name}
    def normalize(self, datum):
        # Normalize against model schema
        schema = self.model_cls.get_schema()
        if schema:
            schema = ModelNormalizer(Schema).normalize(schema)
            datum = schema.normalize(datum)
        # Validate against model's custom validation function
        datum = self.model_cls.validate(datum)
        # Instantiate
        return self.model_cls(datum)

class IntegerNormalizer(Normalizer):
    validates = {u"type": u"integer"}
    def normalize(self, datum):
        """If *datum* is an integer, return it; if it is a float with a 0
        for its fractional part, return the integer part as an
        integer. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == int:
            return datum
        if type(datum) == float and datum.is_integer():
            return int(datum)
        raise ValidationError("Invalid integer", datum)

class FloatNormalizer(Normalizer):
    validates = {u"type": u"float"}
    def normalize(self, datum):
        """If *datum* is a float, return it; if it is an integer, cast it
        to a float and return it. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == float:
            return datum
        if type(datum) == int:
            return float(datum)
        raise ValidationError("Invalid float", datum)

class StringNormalizer(Normalizer):
    validates = {u"type": u"string"}
    def normalize(self, datum):
        """If *datum* is a unicode string, return it. If it is a string,
        decode it as UTF-8 and return the result. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`. Unicode errors are dealt
        with strictly by raising
        :exc:`~cosmic.exceptions.UnicodeDecodeValidationError`, a subclass
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

class BooleanNormalizer(Normalizer):
    validates = {u"type": u"boolean"}
    def normalize(self, datum):
        """If *datum* is a boolean, return it. Otherwise, raise a
        :exc:`~cosmic.exceptions.ValidationError`.
        """
        if type(datum) == bool:
            return datum
        raise ValidationError("Invalid boolean", datum)

class ArrayNormalizer(Normalizer):
    def __init__(self, items_schema):
        self.items = items_schema
    @property
    def validates(self):
        return {
            u"type": u"array",
            u"items": self.items.serialize()
        }
    def normalize(self, datum):
        """If *datum* is a list, construct a new list by running the
        *items* normalization function on each element of *datum*. This
        normalization function may raise
        :exc:`~cosmic.exceptions.ValidationError`. If *datum* is not a list,
        :exc:`~cosmic.exceptions.ValidationError` will be raised.

        .. code::

            >>> normalize_array([1.0, 2, 3.0], normalize_integer)
            [1, 2, 3]

        """
        if type(datum) == list:
            ret = []
            for i, item in enumerate(datum):
                try:
                    ret.append(self.items.normalize(item))
                except ValidationError as e:
                    e.stack.append(i)
                    raise
            return ret
        raise ValidationError("Invalid array", datum)

class ObjectNormalizer(Normalizer):
    def __init__(self, properties):
        self.properties = properties
    @property
    def validates(self):
        props = []
        for prop in self.properties:
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
        """If *datum* is a dict, normalize it against *properties* and
        return the resulting dict. Otherwise raise a
        :exc:`~cosmic.exceptions.ValidationError`.

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

        A :exc:`~cosmic.exceptions.ValidationError` will be raised if:

        1. *datum* is missing a required property
        2. *datum* has a property not declared in *properties*.
        3. One of the properties of *datum* does not pass validation as defined
           by the corresponding *schema* value.

        """
        properties = self.properties
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
        return self.data.validates
    @classmethod
    def validate(self, datum):
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
        wrapping :func:`~cosmic.models.normalize_array` or
        :func:`~cosmic.models.normalize_object`. These can be nested as deep
        as you want, :func:`~cosmic.models.normalize_schema` will recurse::

            >>> normalizer = normalize_schema({
            ...     "type": "array",
            ...     "schema": {"type": "float"}
            ... })
            >>> normalizer([1, 2.2, 3])
            [1.0, 2.2, 3.0]

        """
        datum = Schema(ObjectNormalizer([
            {
                "name": "type",
                "required": True,
                "schema": Schema(StringNormalizer())
            },
            {
                "name": "items",
                "required": False,
                "schema": Schema(ModelNormalizer(Schema))
            },
            {
                "name": "properties",
                "required": False,
                "schema": Schema(ArrayNormalizer(
                    Schema(ObjectNormalizer([
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
                            "schema": Schema(ModelNormalizer(Schema))
                        }
                    ]))
                ))
            }
        ])).normalize(datum)
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
        # Simple type?
        if st == "integer":
            return IntegerNormalizer()
        if st == "float":
            return FloatNormalizer()
        if st == "string":
            return StringNormalizer()
        if st == "boolean":
            return BooleanNormalizer()
        # One of the core models?
        if st == "core.JSON":
            return ModelNormalizer(JSONData)
        if st == "core.Schema":
            return ModelNormalizer(Schema)
        if '.' in st:
            api_name, model_name = st.split('.', 1)
            try:
                api = sys.modules['cosmic.index.' + api_name]
            except KeyError:
                raise ValidationError("Unknown API", api_name)
            try:
                return ModelNormalizer(getattr(api.models, model_name))
            except SpecError:
                raise ValidationError("Unknown model for %s API" % api_name, model_name)
        if st == "array":
            return ArrayNormalizer(datum["items"])
        if st == "object":
            return ObjectNormalizer(datum["properties"])
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

