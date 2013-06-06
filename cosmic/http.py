from __future__ import unicode_literals

import json
import requests

from werkzeug.exceptions import HTTPException, InternalServerError, abort

from flask import Flask, make_response
from flask import request
from teleport import Box, ValidationError

from .tools import *
from .exceptions import *
from . import cosmos


class FlaskView(object):

    def __init__(self, view, debug):
        self.view = view
        self.debug = debug

    def err_to_response(self, err):
        if isinstance(err, HTTPException):
            if err.description != err.__class__.description:
                text = err.description
            else:
                text = err.name
            return self.error_response(text, err.code)
        elif isinstance(err, SpecError):
            return self.error_response(err.args[0], 400)
        elif isinstance(err, ValidationError):
            return self.error_response(str(err), 400)
        else:
            return self.error_response("Internal Server Error", 500)

    def error_response(self, message, code):
        body = json.dumps({"error": message})
        return make_response(body, code, {"Content-Type": "application/json"})

    def __call__(self):
        try:
            ct = request.headers.get('Content-Type', None)
            if request.method != "GET" and ct != "application/json":
                raise SpecError('Content-Type must be "application/json" got %s instead' % ct)
            try:
                request.payload = string_to_json(request.data)
            except ValueError:
                return self.error_response("Invalid JSON", 400)
            with cosmos:
                data = self.view(request.payload)
                body = ""
                if data != None:
                    body = json.dumps(data.datum)
                return make_response(body, 200, {"Content-Type": "application/json"})
        except Exception as err:
            if self.debug:
                raise
            else:
                return self.err_to_response(err)


class Callable(object):

    def __init__(self, function, url):
        self.function = function
        self.url = url

    def __call__(self, *args, **kwargs):
        packed = pack_action_arguments(*args, **kwargs)

        serialized = serialize_json(self.function.accepts, packed)

        data = json_to_string(serialized)

        headers = {'Content-Type': 'application/json'}
        res = requests.post(self.url, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            message = None
            if res.json and 'error' in res.json:
                message = res.json['error']
            abort(res.status_code, message)
        try:
            if self.function.returns and res.content != "":
                return self.function.returns.from_json(res.json)
            else:
                return None
        except ValidationError:
            raise InternalServerError("Call returned an invalid value")
