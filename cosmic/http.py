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
        return make_response(body, code, {})

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
                return make_response(body)
        except Exception as err:
            if self.debug:
                raise
            else:
                return self.err_to_response(err)

