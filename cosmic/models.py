import sys

from werkzeug.local import LocalStack

from teleport import *
from .exceptions import ModelNotFound


class Model(object):
    """A data type definition attached to an API."""

    def __init__(self, data):
        self.data = data

    @classmethod
    def get_schema(cls):
        """Returns the Teleport serializer that describes the structure of the
        data for this model. By default this method will return the
        :attr:`schema` attribute of the :class:`Model` subclass. This is the
        attribute you should override to set the schema.
        """
        return cls.schema

    def serialize_self(self):
        "Returns the JSON form of the model"
        return self.get_schema().serialize(self.data)

    @classmethod
    def deserialize_self(cls, datum):
        """Given the JSON form of the model, deserializes it, validates it and
        instantiates the model.
        """
        datum = cls.get_schema().deserialize(datum)
        return cls.instantiate(datum)

    @classmethod
    def instantiate(cls, datum):
        cls.validate(datum)
        return cls(datum)

    @classmethod # pragma: no cover
    def validate(cls, datum): # pragma: no cover
        """Given the native data as deserialized by :attr:`schema`, validate
        it, raising a :exc:`teleport.exceptions.ValidationError` if the data
        is invalid.
        """


class S(object):
    _model_cls = None

    def __init__(self, model_cls):
        self._model_cls = model_cls

    @property
    def model_cls(self):
        return self._model_cls

    def deserialize(self, datum):
        return self.model_cls.deserialize_self(datum)

    def serialize(self, datum):
        return datum.serialize_self()

    def serialize_self(self):
        model_cls = self.model_cls

        api_name = model_cls.api.name
        model_name = model_cls.__name__
        return {
            "type": u"%s.%s" % (api_name, model_name,)
        }



def get_model_cls(name):
    from . import cosmos
    api_name, model_name = name.split('.', 1)
    try:
        api = cosmos.apis[api_name]
        model = api.models._dict[model_name]
        return model
    except KeyError:
        raise ModelNotFound(name)


class LazyS(S):

    def __init__(self):
        pass

    @property
    def model_cls(self):
        if not self._model_cls:
            self._model_cls = get_model_cls(self._name)
        return self._model_cls


class Cosmos(TypeMap):

    def __init__(self):
        self.lazy_serializers = []
        self.apis = {}

    def force(self):
        for serializer in self.lazy_serializers:
            serializer._model_cls = get_model_cls(serializer._name)
        self.lazy_serializers = []

    def __enter__(self):
        _ctx_stack.push(self)
        super(Cosmos, self).__enter__()

    def __exit__(self, *args, **kwargs):
        _ctx_stack.pop()
        super(Cosmos, self).__exit__(*args, **kwargs)

    def __getitem__(self, name):
        from api import APISerializer, ModelSerializer
        from actions import ActionSerializer
        if name == "cosmic.API":
            return APISerializer
        elif name == "cosmic.Model":
            return ModelSerializer
        elif name == "cosmic.Action":
            return ActionSerializer
        elif '.' in name:

            try:
                class Serializer(S):
                    _model_cls = get_model_cls(name)
                    def __init__(self):
                        pass
                return Serializer
            except ModelNotFound:
                class Serializer(LazyS):
                    _name = name

                self.lazy_serializers.append(Serializer)
                return Serializer
        else:
            return BUILTIN_TYPES[name]

_ctx_stack = LocalStack()
# If the stack is empty, use this global object
_global_cosmos = Cosmos()

