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

