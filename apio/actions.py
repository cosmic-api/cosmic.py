import json

import requests
from flask import request
from flask.exceptions import JSONBadRequest

from apio.tools import get_arg_spec, serialize_action_arguments, apply_to_action_func, JSONPayload
from apio.exceptions import APIError, SpecError

class Action(object):

    def __init__(self, func):
        self.name = func.__name__
        self.spec = {
            "name": self.name,
            "returns": {
                "type": "any"
            }
        }
        self.raw_func = func
        arg_spec = get_arg_spec(func)
        if arg_spec:
            self.spec["accepts"] = arg_spec

    def __call__(self, *args, **kwargs):
        # This seems redundant, but is necessary to make sure local
        # actions behave same as remote ones
        data = serialize_action_arguments(*args, **kwargs)
        return apply_to_action_func(self.raw_func, data)

    def get_view(self, debug=False):
        """Wraps a user-defined action function to return a Flask view function
        that handles errors and returns proper HTTP responses"""
        def action_view():
            if request.headers.get('Content-Type', None) != "application/json":
                return json.dumps({
                    "error": 'Content-Type must be "application/json"'
                }), 400
            # If function takes no arguments, request must be empty
            if 'accepts' not in self.spec and request.data != "":
                return json.dumps({
                    "error": "%s takes no arguments. Request content must be empty" % self.name 
                }), 400
            # If function takes arguments, request cannot be empty
            if 'accepts' in self.spec and request.data == "":
                return json.dumps({
                    "error": "%s takes arguments. Request content cannot be empty" % self.name
                }), 400
            try:
                if request.data == "":
                    data = apply_to_action_func(self.raw_func, None)
                else:
                    data = apply_to_action_func(self.raw_func, JSONPayload(request.json))
            except JSONBadRequest:
                return json.dumps({
                    "error": "Invalid JSON"
                }), 400
            # If the user threw an APIError
            except APIError as err:
                return json.dumps({
                    "error": err.args[0]
                }), err.http_code
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
                raise SpecError("%s takes arguments" % action_name)
            data = ""
        url = self.api_url + '/actions/' + self.spec['name']
        headers = { 'Content-Type': 'application/json' }
        res = requests.post(url, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            raise APIError(res.json['error'])
        return res.json

