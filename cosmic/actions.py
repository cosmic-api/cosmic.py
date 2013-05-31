from __future__ import unicode_literals

import json

import requests
from werkzeug.exceptions import InternalServerError
from teleport import *

from .tools import get_arg_spec, pack_action_arguments, apply_to_func, schema_is_compatible, normalize_json, serialize_json, json_to_string
from .exceptions import SpecError


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
        normalized = normalize_json(self.accepts, payload)
        ret = self.func(normalized)
        return serialize_json(self.returns, ret)
