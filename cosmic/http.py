from __future__ import unicode_literals

import json

from werkzeug.local import LocalProxy, LocalStack, release_local
from werkzeug.wrappers import Request as WerkzeugRequest
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

_request_ctx_stack = LocalStack()


class Request(object):
    """A simplified representation of an HTTP request.

    :param string method: HTTP method
    :param string body: Request body
    :param dict headers: HTTP headers
    """
    def __init__(self, method, body, headers):
        self.method = method
        self.headers = headers
        self.body = body

    def __enter__(self):
        _request_ctx_stack.push(self)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        _request_ctx_stack.pop()


class JSONRequest(Request):
    """If the passed in :class:`~cosmic.http.Request` *req* validates, the
    resulting :class:`JSONRequest` will have a *payload* attribute, storing a
    :class:`~teleport.Box` object or ``None`` if the request body was empty.
    For a non-GET request, Content-Type has to be ``application/json``.

    :param req: :class:`~cosmic.http.Request`
    :raises: :exc:`SpecError`, :exc:`~cosmic.exceptions.JSONParseError`
    """
    def __init__(self, req):
        self.method = req.method
        self.headers = req.headers
        # Make sure Content-Type is application/json, unless the
        # request is GET, in which case just continue
        ct = req.headers.get('Content-Type', None)
        if req.method != "GET" and ct != "application/json":
            raise SpecError('Content-Type must be "application/json" got %s instead' % ct)
        try:
            self.payload = string_to_json(req.body)
        except ValueError:
            # Let's be more specific
            raise JSONParseError()


class FlaskView(object):

    def __init__(self, view):
        self.view = view

    def normalize_request(self, req):
        headers = req.headers
        method = req.method
        body = req.data
        req = Request(method, body, headers)
        return JSONRequest(req)

    def __call__(self, *args, **kwargs):
        req = self.normalize_request(flask_request)
        with req:
            return self.view(req)



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
            req = _request_ctx_stack.top
            # Catch ClientErrors and APIErrors and turn them into responses
            try:
                try:
                    req.context = self.setup_func(req.headers)
                    data = func(req.payload)
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
