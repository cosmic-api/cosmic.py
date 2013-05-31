from __future__ import unicode_literals

from teleport import *

from .tools import deserialize_json, serialize_json


class Function(BasicWrapper):
    type_name = "cosmic.Function"

    schema = Struct([
        optional("accepts", Schema),
        optional("returns", Schema)
    ])

    def __init__(self, accepts=None, returns=None):
        self.accepts = accepts
        self.returns = returns

    @staticmethod
    def inflate(datum):
        return Function(**datum)

    @staticmethod
    def deflate(datum):
        return {
            "accepts": datum.accepts,
            "returns": datum.returns
        }

    def json_to_json(self, payload):
        normalized = deserialize_json(self.accepts, payload)
        ret = self.func(normalized)
        return serialize_json(self.returns, ret)
