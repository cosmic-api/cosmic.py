import json

from flask import request, make_response

from apio.exceptions import *
from apio.tools import JSONPayload, normalize

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
    def __init__(self, headers, body, method):
        self.method = method
        self.headers = headers
        self.body = body

class Response(object):
    def __init__(self, headers, body, code):
        self.headers = headers
        self.body = body
        self.code = code

class View(object):

    def __init__(self, func, accepts=None, returns=None, debug=False, **kwargs):
        self.func = func
        self.methods = kwargs.get("methods", ALL_METHODS)
        self.accepts = accepts
        self.returns = returns
        self.debug = debug

    def flask_view(self, *args, **kwargs):
        headers = request.headers
        method = request.method
        body = request.data
        req = Request(headers, body, method)
        r = self.call(req)
        return make_response(r.body, r.code, r.headers)

    def call(self, req):
        view = cors_middleware(self.methods, self.call_generic)
        return view(req)

    def call_generic(self, req):
        view = standard_middleware(self.methods, self.accepts, self.returns,
                                   self.debug, self.func)
        return view(req)

def standard_middleware(methods, accepts, returns, debug, next_func):
    """Wrap the function with some generic error handling.
    """
    def view(req):
        # Make sure the method is allowed
        if req.method not in methods:
            body = json.dumps({
                "error": "%s is not allowed on this endpoint" % req.method
            })
            return Response({}, body, 405)
        # Make sure Content-Type is right
        ct = req.headers.get('Content-Type', None)
        if ct != "application/json":
            body = json.dumps({
                "error": 'Content-Type must be "application/json"'
            })
            return Response({}, body, 400)
        # Make sure JSON is valid
        try:
            payload = JSONPayload.from_string(req.body)
        except ValueError:
            body = json.dumps({
                "error": "Invalid JSON"
            })
            return Response({}, body, 400)
        # If function takes no arguments, request must be empty
        if accepts == None and payload:
            body = json.dumps({
                "error": "Request content must be empty"
            })
            return Response({}, body, 400)
        # If function takes arguments, request cannot be empty
        if accepts != None and not payload:
            body = json.dumps({
                "error": "Request content cannot be empty"
            })
            return Response({}, body, 400)
        # Validate incoming data
        if payload:
            try:
                normalized = normalize(accepts, payload.json)
                payload = JSONPayload(normalized)
            except ValidationError:
                body = json.dumps({
                    "error": "Validation failed" + json.dumps(accepts)
                })
                return Response({}, body, 400)
        # Try running the actual function
        try:
            data = next_func(payload=payload)
            if returns != None:
                # May raise ValidationError, will be caught below
                data = normalize(returns, data)
                body = json.dumps(data)
                return Response({}, body, 200)
            return Response({}, "", 200)
        except APIError as err:
            body = json.dumps({
                "error": err.args[0]
            })
            return Response({}, body, err.http_code)
        except AuthenticationError:
            body = json.dumps({
                "error": "Authentication failed"
            })
            return Response({}, body, 401)
        # Any other exception should be handled gracefully
        except Exception as e:
            if debug: raise e
            body = json.dumps({
                "error": "Internal Server Error"
            })
            return Response({}, body, 500)
    return view

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
                return Response({}, error, 400)
            # Access-Control-Request-Method is not set or set
            # wrongly?
            requested_method = req.headers.get("Access-Control-Request-Method", None)
            if requested_method not in allowed_methods:
                error = "Access-Control-Request-Method header must be set to "
                error += " or ".join(allowed_methods)
                return Response({}, error, 400)
            # Everything is good, make response
            res_headers = {}
            res_headers["Access-Control-Allow-Origin"] = origin
            res_headers["Access-Control-Allow-Methods"] = ",".join(allowed_methods)
            # Allow all requested headers
            allow_headers = req.headers.get('Access-Control-Request-Headers', None)
            if allow_headers != None:
                res_headers["Access-Control-Allow-Headers"] = allow_headers
            return Response(res_headers, "", 200)
        # Actual request
        res = next_func(req)
        if origin != None:
            res.headers["Access-Control-Allow-Origin"] = origin
        return res
    return view

