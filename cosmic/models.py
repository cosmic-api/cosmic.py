import sys

from teleport import *
from exceptions import ModelNotFound


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
        return cls(datum)

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
    api_name, model_name = name.split('.', 1)
    try:
        # May raise KeyError
        api = sys.modules['cosmic.registry.' + api_name]
        # May raise KeyError
        return api.models._dict[model_name]
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
        self.serializers = {}
        self.lazy_serializers = []

    def force(self):
        for serializer in self.lazy_serializers:
            serializer.force()
            self.serializers[serializer._name] = serializer

    def __getitem__(self, name):
        from api import APISerializer, APIModelSerializer
        from actions import ActionSerializer
        from models import ModelSerializer
        if name == "cosmic.API":
            return APISerializer
        elif name == "cosmic.APIModel":
            return APIModelSerializer
        elif name == "cosmic.Action":
            return ActionSerializer
        elif '.' in name:

            try:
                return self.serializers[name]
            except KeyError:
                class Serializer(LazyModelSerializer):
                    _name = name

                self.lazy_serializers.append(Serializer)
                return Serializer
        else:
            return BUILTIN_TYPES[name]


cosmos = Cosmos()
