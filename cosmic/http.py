from __future__ import unicode_literals

import json

from werkzeug.local import LocalProxy, LocalStack, release_local
from flask import Flask, Blueprint, make_response
from flask import request as flask_request
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
        headers = req.headers
        method = req.method
        body = req.data

        ct = req.headers.get('Content-Type', None)
        if req.method != "GET" and ct != "application/json":
            raise SpecError('Content-Type must be "application/json" got %s instead' % ct)
        try:
            flask_request.payload = string_to_json(req.data)
        except ValueError:
            # Let's be more specific
            raise JSONParseError()

    def __call__(self, *args, **kwargs):
        self.setup_request(flask_request)
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
            # Catch ClientErrors and APIErrors and turn them into responses
            try:
                try:
                    flask_request.context = self.setup_func(flask_request.headers)
                    data = func(flask_request.payload)
                    body = ""
                    if data != None:
                        body = json.dumps(data.datum)
                    return make_response(body)
                except HttpError:
                    raise
                except JSONParseError:
                    raise ClientError("Invalid JSON")
                except SpecError as err:
                    raise ClientError(err.args[0])
                except ValidationError as e:
                    raise ClientError(str(e))
                # Any other exception should be handled gracefully
                except:
                    if self.debug:
                        raise
                    raise APIError("Internal Server Error")
            except HttpError as err:
                return err.get_response()
        return view
