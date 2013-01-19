from __future__ import unicode_literals

import json

from flask import request, make_response

from apio.exceptions import *
from apio.tools import JSONPayload, normalize
from apio.models import serialize_json

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

class Request(object):
    def __init__(self, method, body, headers):
        self.method = method
        self.body = body
        self.headers = headers

class Response(object):
    def __init__(self, code, body, headers):
        self.code = code
        self.body = body
        self.headers = headers

class View(object):

    def __init__(self, func, accepts=None, returns=None, debug=False, methods=None):
        self.func = func
        if methods == None:
            self.methods = ALL_METHODS
        else:
            self.methods = methods
        self.accepts = accepts
        self.returns = returns
        self.debug = debug

    def flask_view(self, *args, **kwargs):
        headers = request.headers
        method = request.method
        body = request.data
        req = Request(method, body, headers)
        view = cors_middleware(self.methods, self)
        r = view(req)
        return make_response(r.body, r.code, r.headers)

    def __call__(self, req):
        # Make sure the method is allowed
        if req.method not in self.methods:
            body = json.dumps({
                "error": "%s is not allowed on this endpoint" % req.method
            })
            return Response(405, body, {})
        # Make sure Content-Type is right
        ct = req.headers.get('Content-Type', None)
        if ct != "application/json":
            body = json.dumps({
                "error": 'Content-Type must be "application/json"'
            })
            return Response(400, body, {})
        # Make sure JSON is valid
        try:
            payload = JSONPayload.from_string(req.body)
        except ValueError:
            body = json.dumps({
                "error": "Invalid JSON"
            })
            return Response(400, body, {})
        # If function takes no arguments, request must be empty
        if self.accepts == None and payload:
            body = json.dumps({
                "error": "Request content must be empty"
            })
            return Response(400, body, {})
        # If function takes arguments, request cannot be empty
        if self.accepts != None and not payload:
            body = json.dumps({
                "error": "Request content cannot be empty"
            })
            return Response(400, body, {})
        # Validate incoming data
        if payload:
            try:
                normalized = normalize(self.accepts, payload.json)
                payload = JSONPayload(normalized)
            except ValidationError:
                body = json.dumps({
                    "error": "Validation failed" + json.dumps(self.accepts)
                })
                return Response(400, body, {})
        # Try running the actual function
        try:
            data = self.func(payload)
            if self.returns != None:
                # May raise ValidationError, will be caught below
                data = normalize(self.returns, data)
                body = json.dumps(serialize_json(data))
                return Response(200, body, {})
            return Response(200, "", {})
        except APIError as err:
            body = json.dumps({
                "error": err.args[0]
            })
            return Response(err.http_code, body, {})
        except AuthenticationError:
            body = json.dumps({
                "error": "Authentication failed"
            })
            return Response(401, body, {})
        # Any other exception should be handled gracefully
        except:
            if self.debug:
                raise
            body = json.dumps({
                "error": "Internal Server Error"
            })
            return Response(500, body, {})
        return view(req)

def cors_middleware(allowed_methods, next_func):
    """Takes a Flask view function and augments it with CORS
    functionality. Implementation based on this tutorial:
    http://www.html5rocks.com/en/tutorials/cors/

    Access-Control-Allow-Credentials can be emulated, so there's no
    real reason to support it. IE doesn't support wildcard
    Access-Control-Allow-Origin so we just echo the request Origin
    instead. See here for notes:
    https://github.com/alexandru/crossdomain-requests-js/wiki/Troubleshooting

    Note that many CORS implementations are broken. For example,
    see: http://stackoverflow.com/q/12780839/212584
    """
    def view(req):
        origin = req.headers.get("Origin", None)
        # Preflight request
        if req.method == "OPTIONS":
            # No Origin?
            if origin == None:
                error = "Preflight CORS request must include Origin header"
                return Response(400, error, {})
            # Access-Control-Request-Method is not set or set wrongly?
            requested_method = req.headers.get("Access-Control-Request-Method", None)
            if requested_method not in allowed_methods:
                error = "Access-Control-Request-Method header must be set to "
                error += " or ".join(allowed_methods)
                return Response(400, error, {})
            # Everything is good, make response
            res_headers = {}
            res_headers["Access-Control-Allow-Origin"] = origin
            res_headers["Access-Control-Allow-Methods"] = ",".join(allowed_methods)
            # Allow all requested headers
            allow_headers = req.headers.get('Access-Control-Request-Headers', None)
            if allow_headers != None:
                res_headers["Access-Control-Allow-Headers"] = allow_headers
            return Response(200, "", res_headers)
        # Actual request
        res = next_func(req)
        if origin != None:
            res.headers["Access-Control-Allow-Origin"] = origin
        return res
    return view

