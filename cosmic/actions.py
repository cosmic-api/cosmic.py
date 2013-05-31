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


class Action(BasicWrapper):
    type_name = "cosmic.Action"

    schema = Struct([
        required("name", String),
        optional("accepts", Schema),
        optional("returns", Schema)
    ])

    def __init__(self, name, accepts=None, returns=None, raw_func=None):
        self.name = name
        self.accepts = accepts
        self.returns = returns
        self.raw_func = raw_func

    @staticmethod
    def inflate(datum):
        return Action(**datum)

    @staticmethod
    def deflate(datum):
        return {
            "name": datum.name,
            "accepts": datum.accepts,
            "returns": datum.returns
        }

    @classmethod
    def from_func(cls, func, accepts=None, returns=None):
        """Create an action from a function *func* that expects data as
        defined by the *accepts* schema and returns data that will be
        serialized by the *returns* schema. Both *accepts* and *returns* must
        be Teleport serializers.
        """
        name = func.__name__
        arg_spec = get_arg_spec(func)

        if accepts:
            if not arg_spec:
                raise SpecError("'%s' is said to take arguments, but doesn't" % name)
            if not schema_is_compatible(arg_spec, accepts):
                raise SpecError("The accepts parameter of '%s' action is incompatible with the function's arguments")

        return cls(
            name=name,
            accepts=accepts,
            returns=returns,
            raw_func=func)

    def json_to_json(self, payload):
        normalized = normalize_json(self.accepts, payload)
        ret = self(normalized)
        return serialize_json(self.returns, ret)

    def __call__(self, *args, **kwargs):
        """If action was generated from a function, calls it with the passed
        in data, otherwise serializes the data, makes an HTTP request to the
        API and returns its normalized response.

        Uses :func:`~cosmic.tools.pack_action_arguments`.
        """
        packed = pack_action_arguments(*args, **kwargs)

        if self.raw_func != None:
            # It may seem reduntant to pack then unpack arguments, but we need
            # to make sure local actions behave same as remote ones
            return apply_to_func(self.raw_func, packed)

        serialized = serialize_json(self.accepts, packed)
        # Try to normalize, just for the sake of validation
        normalize_json(self.accepts, serialized)

        data = json_to_string(serialized)

        url = self.api.url + '/actions/' + self.name
        headers = {'Content-Type': 'application/json'}
        res = requests.post(url, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            if res.json and 'error' in res.json:
                raise InternalServerError(res.json['error'])
            else:
                raise InternalServerError("Call to %s failed with improper error response")
        try:
            if self.returns:
                return self.returns.from_json(res.json)
            else:
                return None
        except ValidationError:
            raise InternalServerError("Call to %s returned an invalid value" % self.name)

