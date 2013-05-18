from __future__ import unicode_literals

import json

from werkzeug.local import LocalProxy, LocalStack, release_local
from werkzeug.exceptions import HTTPException, Unauthorized, BadRequest, InternalServerError
from flask import Flask, Blueprint, make_response
from flask import request
from teleport import Box, ValidationError

from .tools import json_to_string, string_to_json
from .exceptions import *
from . import cosmos


class FlaskView(object):

    def __init__(self, view, setup_func, debug):
        self.view = view
        self.setup_func = setup_func
        self.debug = debug

    def err_to_response(self, err):
        if isinstance(err, HTTPException):
            if err.description != err.__class__.description:
                text = err.description
            else:
                text = err.name
            body = {"error": text}
            code = err.code
        elif isinstance(err, JSONParseError):
            body = {"error": "Invalid JSON"}
            code = 400
        elif isinstance(err, SpecError):
            body = {"error": err.args[0]}
            code = 400
        elif isinstance(err, ValidationError):
            body = {"error": str(err)}
            code = 400
        else:
            body = {"error": "Internal Server Error"}
            code = 500
        return make_response(json.dumps(body), code, {})

    def __call__(self):
        try:
            ct = request.headers.get('Content-Type', None)
            if request.method != "GET" and ct != "application/json":
                raise SpecError('Content-Type must be "application/json" got %s instead' % ct)
            try:
                request.payload = string_to_json(request.data)
            except ValueError:
                # Let's be more specific
                raise JSONParseError()
            with cosmos:
                request.context = self.setup_func(request.headers)
                data = self.view(request.payload)
                body = ""
                if data != None:
                    body = json.dumps(data.datum)
                return make_response(body)
        except Exception as err:
            if self.debug:
                raise
            else:
                return self.err_to_response(err)

