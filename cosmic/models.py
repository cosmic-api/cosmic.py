import sys

from werkzeug.local import LocalStack

from teleport import *
from .exceptions import ModelNotFound


class Model(object):

    def __init__(self, data):
        self.data = data

    def serialize_self(self):
        return self.get_schema().serialize(self.data)

    @classmethod
    def deserialize_self(cls, datum):
        datum = cls.get_schema().deserialize(datum)
        return cls.instantiate(datum)

    @classmethod
    def instantiate(cls, datum):
        cls.validate(datum)
        return cls(datum)

    @classmethod
    def validate(cls, datum):
        pass

    @classmethod
    def get_schema(cls):
        return cls.schema


class ModelSerializer(object):

    def __init__(self, model_cls):
        self.model_cls = model_cls

    def deserialize(self, datum):
        return self.model_cls.deserialize_self(datum)

    def serialize(self, datum):
        return datum.serialize_self()

    def serialize_self(self):
        api_name = self.model_cls.api.name
        model_name = self.model_cls.__name__
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


class LazyModelSerializer(ModelSerializer):

    def __init__(self):
        pass

    @classmethod
    def force(cls):
        cls.model_cls = get_model_cls(cls._name)

    def deserialize(self, datum):
        self.force()
        return super(LazyModelSerializer, self).deserialize(datum)

    def serialize(self, datum):
        self.force()
        return super(LazyModelSerializer, self).serialize(datum)

    def serialize_self(self):
        self.force()
        return super(LazyModelSerializer, self).serialize_self(datum)


class Cosmos(TypeMap):

    def __init__(self):
        self.lazy_serializers = []
        self.apis = {}

    def force(self):
        for serializer in self.lazy_serializers:
            serializer.force()
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
        from models import ModelSerializer
        if name == "cosmic.API":
            return APISerializer
        elif name == "cosmic.Model":
            return ModelSerializer
        elif name == "cosmic.Action":
            return ActionSerializer
        elif '.' in name:

            try:
                class Serializer(ModelSerializer):
                    model_cls = get_model_cls(name)
                    def __init__(self):
                        pass
                return Serializer
            except ModelNotFound:
                class Serializer(LazyModelSerializer):
                    _name = name

                self.lazy_serializers.append(Serializer)
                return Serializer
        else:
            return BUILTIN_TYPES[name]

_ctx_stack = LocalStack()
_ctx_stack.push(Cosmos())

