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

    def get_flask_view(self):
        def view(*args, **kwargs):
            headers = request.headers
            method = request.method
            body = request.data
            req = Request(headers, body, method)
            r = self.call(req)
            return make_response(r.body, r.code, r.headers)
        return view

    def call(self, req):
        view = cors_middleware(self.methods, self.call_generic)
        return view(req)

    def call_generic(self, req):
        # Make sure the method is allowed
        if req.method not in self.methods:
            body = json.dumps({
                "error": "%s is not allowed on this endpoint" % request.method
            })
            return Response({}, body, 401)
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
        if self.accepts == None and payload:
            body = json.dumps({
                "error": "Request content must be empty"
            })
            return Response({}, body, 400)
        # If function takes arguments, request cannot be empty
        if self.accepts != None and not payload:
            body = json.dumps({
                "error": "Request content cannot be empty"
            })
            return Response({}, body, 400)
        # Validate incoming data
        if payload:
            try:
                normalized = normalize(self.accepts, payload.json)
                payload = JSONPayload(normalized)
            except ValidationError:
                body = json.dumps({
                    "error": "Validation failed" + json.dumps(accepts)
                })
                return Response({}, body, 400)
        # Try running the actual function
        try:
            data = self.func(payload=payload)
            if self.returns != None:
                # May raise ValidationError, will be caught below
                data = normalize(self.returns, data)
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
            if self.debug: raise e
            body = json.dumps({
                "error": "Internal Server Error"
            })
            return Response({}, body, 500)


def cors_middleware(allowed_methods, next_func):
    """Flask view for handling the CORS preflight request
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


def corsify_view(allowed_methods):
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
    def decorator(view_func):
        def corsified(*args, **kwargs):
            """Flask view for handling the CORS preflight request
            """
            headers = request.headers
            method = request.method

            origin = headers.get("Origin", None)
            # Preflight request
            if method == "OPTIONS":
                # No Origin?
                if origin == None:
                    error = "Preflight CORS request must include Origin header"
                    return error, 400
                # Access-Control-Request-Method is not set or set
                # wrongly?
                requested_method = headers.get("Access-Control-Request-Method", None)
                if requested_method not in allowed_methods:
                    error = "Access-Control-Request-Method header must be set to "
                    error += " or ".join(allowed_methods)
                    return error, 400
                # Everything is good, make response
                res = make_response("", 200)
                res.headers["Access-Control-Allow-Origin"] = origin
                res.headers["Access-Control-Allow-Methods"] = ",".join(allowed_methods)
                # Allow all requested headers
                res_headers = headers.get('Access-Control-Request-Headers', None)
                if res_headers != None:
                    res.headers["Access-Control-Allow-Headers"] = res_headers
            # Actual request
            else:
                # If view_func returns a tuple, make_response will
                # turn it into flask.Response. If it already returns a
                # Response, make_response will do nothing
                res = make_response(view_func(*args, **kwargs))
                if origin != None:
                    res.headers["Access-Control-Allow-Origin"] = origin
            return res
        return corsified
    return decorator

def apio_view(methods, debug=False, accepts=None, returns=None):
    """Wraps the function with some generic error handling
    """
    def wrapper(view_func):
        @corsify_view(methods)
        def wrapped():
            # Make sure the method is allowed
            if request.method not in methods:
                return json.dumps({
                    "error": "%s is not allowed on this endpoint" % request.method
                }), 405
            # Make sure Content-Type is right
            ct = request.headers.get('Content-Type', None)
            if ct != "application/json":
                return json.dumps({
                    "error": 'Content-Type must be "application/json"'
                }), 400
            # Make sure JSON is valid
            try:
                payload = JSONPayload.from_string(request.data)
            except ValueError:
                return json.dumps({
                    "error": "Invalid JSON"
                }), 400
            # If function takes no arguments, request must be empty
            if accepts == None and payload:
                return json.dumps({
                    "error": "Request content must be empty"
                }), 400
            # If function takes arguments, request cannot be empty
            if accepts != None and not payload:
                return json.dumps({
                    "error": "Request content cannot be empty"
                }), 400
            # Validate incoming data
            if payload:
                try:
                    normalized = normalize(accepts, payload.json)
                    payload = JSONPayload(normalized)
                except ValidationError:
                    return json.dumps({
                        "error": "Validation failed" + json.dumps(accepts)
                    }), 400
            # Try running the actual function
            try:
                data = view_func(payload=payload)
                if returns != None:
                    # May raise ValidationError, will be caught below
                    data = normalize(returns, data)
                    return json.dumps(data), 200
                return "", 200
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
        return wrapped
    return wrapper
