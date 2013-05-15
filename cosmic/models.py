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
        return {
            "type": unicode(self.model_cls.__name__)
        }


