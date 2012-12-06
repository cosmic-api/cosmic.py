import json

import requests
from flask import request
from flask.exceptions import JSONBadRequest

from apio.tools import get_arg_spec, serialize_action_arguments, apply_to_action_func, JSONPayload, schema_is_compatible
from apio.exceptions import APIError, SpecError, AuthenticationError

class Action(object):

    def __init__(self, func, accepts=None, returns=None):
        self.name = func.__name__
        if not returns:
            returns = { "type": "any" }

        self.spec = {
            "name": self.name,
            "returns": returns
        }
        self.raw_func = func
        arg_spec = get_arg_spec(func)

        # if accepts:
        #     try:
        #         validate(Draft3Validator.META_SCHEMA, accepts)
        #     except SchemaError:
        #         raise SpecError("'%s' was passed an invalid accepts schema" % self.name)

        if not arg_spec and not accepts:
            return

        if arg_spec and not accepts:
            accepts = arg_spec

        if not arg_spec and accepts:
            raise SpecError("'%s' is said to take arguments, but doesn't" % self.name)

        if arg_spec and accepts:
            if not schema_is_compatible(arg_spec, accepts):
                raise SpecError("The accepts parameter of '%s' action is incompatible with the function's arguments")

        if accepts:
            self.spec["accepts"] = accepts

    def __call__(self, *args, **kwargs):
        # This seems redundant, but is necessary to make sure local
        # actions behave same as remote ones
        data = serialize_action_arguments(*args, **kwargs)
        return apply_to_action_func(self.raw_func, data)

    def get_view(self, debug=False):
        """Wraps a user-defined action function to return a Flask view function
        that handles errors and returns proper HTTP responses"""
        def action_view():
            ct = request.headers.get('Content-Type', None)
            cto = request.args.get('content_type_override', None)
            if (cto and cto != "application/json") or (not cto and ct != "application/json"):
                return json.dumps({
                    "error": 'Content-Type must be "application/json"'
                }), 400
            try:
                payload = JSONPayload.from_string(request.data)
            except ValueError:
                return json.dumps({
                    "error": "Invalid JSON"
                }), 400
            # If function takes no arguments, request must be empty
            if 'accepts' not in self.spec and payload:
                return json.dumps({
                    "error": "%s takes no arguments. Request content must be empty" % self.name 
                }), 400
            # If function takes arguments, request cannot be empty
            if 'accepts' in self.spec and not payload:
                return json.dumps({
                    "error": "%s takes arguments. Request content cannot be empty" % self.name
                }), 400
            try:
                data = apply_to_action_func(self.raw_func, payload)
            # If the user threw an APIError
            except APIError as err:
                return json.dumps({
                    "error": err.args[0]
                }), err.http_code
            except AuthenticationError:
                return json.dumps({
                    "error": "Authentication failed"
                }), 401
            # Any other exception should be handled gracefully
            except Exception as e:
                if debug: raise e
                return json.dumps({
                    "error": "Internal Server Error"
                }), 500
            return json.dumps(data)
        return action_view


class RemoteAction(object):

    def __init__(self, spec, api_url):
        self.spec = spec
        self.api_url = api_url

    def __call__(self, *args, **kwargs):
        json_data = serialize_action_arguments(*args, **kwargs)
        if json_data:
            data = json.dumps(json_data.json)
        else:
            if 'accepts' in self.spec:
                raise SpecError("%s takes arguments" % self.spec['name'])
            data = ""
        url = self.api_url + '/actions/' + self.spec['name']
        headers = { 'Content-Type': 'application/json' }
        res = requests.post(url, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            if res.json and 'error' in res.json:
                raise APIError(res.json['error'])
            else:
                raise APIError("Call to %s failed with improper error response")
        return res.json

