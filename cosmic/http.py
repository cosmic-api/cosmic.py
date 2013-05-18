from __future__ import unicode_literals

import json

from werkzeug.local import LocalProxy, LocalStack, release_local
from werkzeug.exceptions import HTTPException, Unauthorized, BadRequest, InternalServerError
from flask import Flask, Blueprint, make_response
from flask import request
from teleport import Box, ValidationError

from .tools import json_to_string, string_to_json
from .exceptions import *


# We shouldn't have to do this, but Flask doesn't allow us to route
# all methods implicitly. When we don't pass in methods Flask assumes
# methods to be ["GET", "HEAD", "OPTIONS"].
ALL_METHODS = [
    "OPTIONS",
    "GET",
    "HEAD",
    "POST",
    "PUT",
    "DELETE",
    "TRACE",
    "CONNECT"
]


class FlaskView(object):

    def __init__(self, view):
        self.view = view

    def setup_request(self, req):
        ct = req.headers.get('Content-Type', None)
        if req.method != "GET" and ct != "application/json":
            raise SpecError('Content-Type must be "application/json" got %s instead' % ct)
        try:
            request.payload = string_to_json(req.data)
        except ValueError:
            # Let's be more specific
            raise JSONParseError()

    def __call__(self, *args, **kwargs):
        self.setup_request(request)
        return self.view()


class FlaskPlugin(object):

    def __init__(self, setup_func, url_prefix="", debug=False, werkzeug_map=None):
        self.setup_func = setup_func
        self.app = Flask(__name__, static_folder=None)
        self.debug = debug
        for rule in werkzeug_map.iter_rules():

            v = self.make_view(rule.endpoint)

            url = url_prefix + rule.rule
            self.app.add_url_rule(url,
                view_func=FlaskView(v),
                methods=rule.methods,
                endpoint=rule.endpoint.__name__)

    def make_view(self, func):
        def view(*args, **kwargs):
            # Catch 400s and 500s and turn them into responses
            try:
                try:
                    request.context = self.setup_func(request.headers)
                    data = func(request.payload)
                    body = ""
                    if data != None:
                        body = json.dumps(data.datum)
                    return make_response(body)
                except HTTPException:
                    raise
                except JSONParseError:
                    raise BadRequest("Invalid JSON")
                except SpecError as err:
                    raise BadRequest(err.args[0])
                except ValidationError as e:
                    raise BadRequest(str(e))
                # Any other exception should be handled gracefully
                except:
                    if self.debug:
                        raise
                    raise InternalServerError()
            except HTTPException as err:
                if err.description != err.__class__.description:
                    text = err.description
                else:
                    text = err.name
                body = json.dumps({"error": text})
                return make_response(body, err.code, {})
        return view
