from __future__ import unicode_literals

from teleport import BasicWrapper

from .types import *


class Action(BasicWrapper):
    type_name = "cosmic.Action"

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
        return Action(**datum)

    @staticmethod
    def disassemble(datum):
        return {
            "accepts": datum.accepts,
            "returns": datum.returns,
            "doc": datum.doc
        }

    def __call__(self, *args, **kwargs):
        if hasattr(self, "func"):
            return self.func(*args, **kwargs)
        return self.endpoint(*args, **kwargs)

