import json

import requests
from flask import request
from flask.exceptions import JSONBadRequest

from apio.tools import get_arg_spec, serialize_action_arguments, apply_to_action_func, JSONPayload, schema_is_compatible, normalize, corsify_view, apio_view
from apio.exceptions import APIError, SpecError, AuthenticationError, ValidationError

class Action(object):

    def __init__(self, func, accepts=None, returns=None):
        self.name = func.__name__

        self.spec = {
            "name": self.name
        }
        self.raw_func = func
        arg_spec = get_arg_spec(func)

        if accepts:
            if not arg_spec:
                raise SpecError("'%s' is said to take arguments, but doesn't" % self.name)

            try:
                accepts = normalize({"type": "schema"}, accepts)
            except ValidationError:
                raise SpecError("'%s' was passed an invalid accepts schema" % self.name)

            if not schema_is_compatible(arg_spec, accepts):
                raise SpecError("The accepts parameter of '%s' action is incompatible with the function's arguments")
        elif arg_spec:
            accepts = arg_spec

        if returns:
            try:
                self.spec["returns"] = normalize({"type": "schema"}, returns)
            except ValidationError:
                raise SpecError("'%s' was passed an invalid returns schema" % self.name)
        else:
            self.spec["returns"] = { "type": "any" }

        if accepts:
            self.spec["accepts"] = accepts

    def __call__(self, *args, **kwargs):
        # This seems redundant, but is necessary to make sure local
        # actions behave same as remote ones
        data = serialize_action_arguments(*args, **kwargs)
        return apply_to_action_func(self.raw_func, data)

    def add_to_blueprint(self, blueprint, debug=False):
        name = self.spec['name']
        view = self.get_view(debug=debug)
        view = corsify_view(["POST"])(view)
        url = "/actions/%s" % name
        blueprint.add_url_rule(url, name, view, methods=['POST', 'OPTIONS'])

    def get_view(self, debug=False):
        """Wraps a user-defined action function to return a Flask view function
        that handles errors and returns proper HTTP responses"""
        accepts = self.spec.get('accepts', None)
        returns = self.spec.get('returns', None)
        @apio_view(debug=debug, accepts=accepts, returns=returns)
        def action_view(payload):
            return apply_to_action_func(self.raw_func, payload)
        return action_view


class RemoteAction(object):

    def __init__(self, spec, api_url):
        self.spec = spec
        self.api_url = api_url

    def __call__(self, *args, **kwargs):
        json_data = serialize_action_arguments(*args, **kwargs)
        if not json_data and 'accepts' in self.spec:
            raise SpecError("%s takes arguments" % self.spec['name'])
        if json_data:
            try:
                normalized = normalize(self.spec['accepts'], json_data.json)
                json_data = JSONPayload(normalized)
            except ValidationError as err:
                raise SpecError(err.args[0])
            data = json.dumps(json_data.json)
        else:
            data = ""
        url = self.api_url + '/actions/' + self.spec['name']
        headers = { 'Content-Type': 'application/json' }
        res = requests.post(url, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            if res.json and 'error' in res.json:
                raise APIError(res.json['error'])
            else:
                raise APIError("Call to %s failed with improper error response")
        try:
            return normalize(self.spec['returns'], res.json)
        except ValidationError:
            raise APIError("Call to %s returned an invalid value" % self.spec['name'])
