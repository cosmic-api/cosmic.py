from __future__ import unicode_literals

import json

import requests

from cosmic.tools import get_arg_spec, pack_action_arguments, apply_to_func, schema_is_compatible, normalize, normalize_schema, fetch_model
from cosmic.http import ALL_METHODS, View, make_view
from cosmic.exceptions import APIError, SpecError, AuthenticationError, ValidationError

from cosmic.models import *

class Action(ClassModel):

    properties = [
        {
            "name": "name",
            "schema": normalize_schema({"type": "string"}),
            "required": True
        },
        {
            "name": "accepts",
            "schema": normalize_schema({"type": "schema"}),
            "required": False
        },
        {
            "name": "returns",
            "schema": normalize_schema({"type": "schema"}),
            "required": False
        }
    ]

    def get_view(self, debug=False):
        """Wraps a user-defined action function to return a Flask view function
        that handles errors and returns proper HTTP responses"""
        accepts = self.accepts
        if accepts:
            accepts = accepts.serialize()
        returns = self.returns
        if returns:
            returns = returns.serialize()
        @make_view("POST", accepts=accepts, returns=returns)
        def action_view(payload):
            return apply_to_func(self.raw_func, payload.data)
        return action_view

    def __call__(self, *args, **kwargs):
        packed = pack_action_arguments(*args, **kwargs)

        if not packed and self.accepts:
            raise SpecError("%s takes arguments" % self.name)

        if packed:
            serialized = self.accepts.serialize_data(packed)
            # Try to normalize, just for the sake of validation
            try:
                self.accepts.normalize_data(serialized, fetcher=fetch_model)
            except ValidationError as err:
                raise SpecError(err.args[0])

        if hasattr(self, "raw_func"):
            # This seems redundant, but is necessary to make sure local
            # actions behave same as remote ones
            return apply_to_func(self.raw_func, packed)
        else:
            if packed:
                data = json.dumps(serialized)
            else:
                data = ""
            
            url = self.api_url + '/actions/' + self.name
            headers = {'Content-Type': 'application/json'}
            res = requests.post(url, data=data, headers=headers)
            if res.status_code != requests.codes.ok:
                if res.json and 'error' in res.json:
                    raise APIError(res.json['error'])
                else:
                    raise APIError("Call to %s failed with improper error response")
            try:
                if self.returns:
                    return self.returns.normalize_data(res.json, fetcher=fetch_model)
                else:
                    return None
            except ValidationError:
                raise APIError("Call to %s returned an invalid value" % self.name)

    @classmethod
    def from_func(cls, func, accepts=None, returns=None):

        name = func.__name__
        arg_spec = get_arg_spec(func)

        if accepts:
            if not arg_spec:
                raise SpecError("'%s' is said to take arguments, but doesn't" % name)
            if not schema_is_compatible(arg_spec, accepts):
                raise SpecError("The accepts parameter of '%s' action is incompatible with the function's arguments")

        return cls({
            "name": name,
            "accepts": accepts,
            "returns": returns
        }, raw_func=func)
