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


    @classmethod
    def from_func(cls, func, accepts=None, returns=None):
        """Create an action from a function *func* that expects data as
        normalized by the *accepts* schema and returns data that will be
        serialized by the *returns* schema. Both *accepts* and *returns* must
        be :class:`~cosmic.models.Schema` instances.
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


    def get_view(self, debug=False):
        """Wraps a user-defined action function to return a Flask view function
        that handles errors and returns proper HTTP responses"""
        @make_view("POST")
        def action_view(payload):
            normalized = normalize_json(self.accepts, payload)
            ret = apply_to_func(self.raw_func, normalized)
            return serialize_json(self.returns, ret)
        return action_view


    def __call__(self, *args, **kwargs):
        """If action was generated from a function, calls it with the passed
        in data, otherwise serializes the data, makes an HTTP request to the
        API and returns its normalized response.

        Uses :func:`~cosmic.tools.pack_action_arguments`.
        """
        packed = pack_action_arguments(*args, **kwargs)

        if hasattr(self, "raw_func"):
            # It may seem reduntant to pack then unpack arguments, but we need
            # to make sure local actions behave same as remote ones
            return apply_to_func(self.raw_func, packed)

        serialized = serialize_json(self.accepts, packed)
        # Try to normalize, just for the sake of validation
        normalize_json(self.accepts, serialized)

        data = JSONData.to_string(serialized)

        url = self.api.url + '/actions/' + self.name
        headers = {'Content-Type': 'application/json'}
        res = requests.post(url, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            if res.json and 'error' in res.json:
                raise APIError(res.json['error'])
            else:
                raise APIError("Call to %s failed with improper error response")
        try:
            if self.returns:
                return self.returns.normalize_data(res.json)
            else:
                return None
        except ValidationError:
            raise APIError("Call to %s returned an invalid value" % self.name)
