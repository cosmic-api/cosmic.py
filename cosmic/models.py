import sys

from teleport import *


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


class Cosmos(TypeMap):

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
            api_name, model_name = name.split('.', 1)
            # May raise KeyError
            api = sys.modules['cosmic.registry.' + api_name]
            model = api.models._dict[model_name]

            class Serializer(ModelSerializer):
                model_cls = model
                def __init__(self):
                    pass

            return Serializer
        else:
            return BUILTIN_TYPES[name]


cosmos = Cosmos()
