from __future__ import unicode_literals

from teleport import *

from .tools import deserialize_json, serialize_json


class Function(BasicWrapper):
    type_name = "cosmic.Function"

    schema = Struct([
        optional("accepts", Schema),
        optional("returns", Schema),
        optional("doc", String)
    ])

    def __init__(self, accepts=None, returns=None, doc=None):
        self.accepts = accepts
        self.returns = returns
        self.doc = doc

    @staticmethod
    def assemble(datum):
        return Function(**datum)

    @staticmethod
    def disassemble(datum):
        return {
            "accepts": datum.accepts,
            "returns": datum.returns,
            "doc": datum.doc
        }

    def json_to_json(self, payload):
        normalized = deserialize_json(self.accepts, payload)
        ret = self.func(normalized)
        return serialize_json(self.returns, ret)
