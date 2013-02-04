from __future__ import unicode_literals

import json

import requests

from cosmic.tools import get_arg_spec, serialize_action_arguments, apply_to_action_func, schema_is_compatible, normalize, CosmicSchema
from cosmic.http import ALL_METHODS, View, make_view
from cosmic.exceptions import APIError, SpecError, AuthenticationError, ValidationError

from cosmic.models import serialize_json, JSONData, ObjectModel

class BaseAction(ObjectModel):
    _name = "cosmic.Action"
    properties = [
        {
            "name": "name",
            "schema": {"type": "string"},
            "required": True
        },
        {
            "name": "accepts",
            "schema": {"type": "core.Schema"},
            "required": False
        },
        {
            "name": "returns",
            "schema": {"type": "core.Schema"},
            "required": False
        }
    ]


class Action(BaseAction):

    def __init__(self, func, accepts=None, returns=None):

        self.raw_func = func
        name = func.__name__
        arg_spec = get_arg_spec(func)

        if accepts:
            if not arg_spec:
                raise SpecError("'%s' is said to take arguments, but doesn't" % name)
            if not schema_is_compatible(arg_spec, accepts):
                raise SpecError("The accepts parameter of '%s' action is incompatible with the function's arguments")
        elif arg_spec:
            accepts = arg_spec

        super(Action, self).__init__({
            "name": name,
            "accepts": accepts,
            "returns": returns
        })

    def __call__(self, *args, **kwargs):
        # This seems redundant, but is necessary to make sure local
        # actions behave same as remote ones
        data = serialize_action_arguments(*args, **kwargs)
        return apply_to_action_func(self.raw_func, data)

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
            return apply_to_action_func(self.raw_func, payload)
        return action_view


class RemoteAction(BaseAction):

    def __call__(self, *args, **kwargs):
        json_data = serialize_action_arguments(*args, **kwargs)
        if not json_data and self.accepts:
            raise SpecError("%s takes arguments" % self.name)
        if json_data:
            try:
                normalized = self.accepts.normalize(json_data.data)
            except ValidationError as err:
                raise SpecError(err.args[0])
            serialized = serialize_json(normalized)
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
                return self.returns.normalize(res.json)
            else:
                return None
        except ValidationError:
            raise APIError("Call to %s returned an invalid value" % self.name)

# When deserializing, we want an instance of RemoteAction
CosmicSchema.builtin_models["cosmic.Action"] = RemoteAction
