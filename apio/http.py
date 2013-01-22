from __future__ import unicode_literals

import json

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
        self.headers = headers
        self.body = body

class JSONRequest(Request):
    """Turn a :class:`~apio.http.Request` into a
    :class:`~apio.http.JSONRequest`

    :raises: :exc:`SpecError`, :exc:`~apio.exceptions.JSONParseError`
    """
    def __init__(self, req):
        self.method = req.method
        self.headers = req.headers
        # Make sure Content-Type is application/json, unless the
        # request is GET, in which case just continue
        ct = req.headers.get('Content-Type', None)
        if req.method != "GET" and ct != "application/json":
            raise SpecError('Content-Type must be "application/json"')
        try:
            self.payload = JSONPayload.from_string(req.body)
        except ValueError:
            # Let's be more specific
            raise JSONParseError()

class Response(object):
    def __init__(self, code, body="", headers={}):
        self.code = code
        self.body = body
        self.headers = headers

class View(object):

    def __init__(self, func, method, accepts=None, returns=None):
        self.func = func
        self.method = method
        self.accepts = accepts
        self.returns = returns

    def __call__(self, req, debug=False):
        res = Response(200)
        # Necessary for CORS
        if "Origin" in req.headers:
            res.headers["Access-Control-Allow-Origin"] = req.headers["Origin"]
        # Catch ClientErrors and APIErrors and turn them into Responses
        try:
            # Validate request
            try:
                req = self.validate_request(req)
            except SpecError as err:
                raise ClientError(err.args[0])
            except JSONParseError:
                raise ClientError("Invalid JSON")
            except ValidationError as e:
                raise ClientError(e.print_json())
            # Run the actual function
            try:
                data = self.func(req.payload)
                # May raise ValidationError, will be caught below and
                # rethrown if we are in debug mode
                if self.returns:
                    data = normalize(self.returns, data)
                    res.body = json.dumps(serialize_json(data))
                # Likewise, will be rethrown in debug mode
                elif data != None:
                    raise SpecError("None expected, but the function returned %s instead" % (data))
                return res
            except HttpError:
                raise
            except AuthenticationError:
                raise ClientError("Authentication failed", http_code=401)
            # Any other exception should be handled gracefully
            except:
                if debug:
                    raise
                raise APIError("Internal Server Error")
        except HttpError as err:
            return err.get_response()

    def validate_request(self, req):
        req = JSONRequest(req)
        # If function takes no arguments, request must be empty
        if self.accepts == None and req.payload:
            raise SpecError("Request content must be empty")
        # If function takes arguments, request cannot be empty
        if self.accepts != None and not req.payload:
            raise SpecError("Request content cannot be empty")
        # Validate incoming data
        if req.payload:
            normalize(self.accepts, req.payload.json)
        return req

def make_view(method, accepts=None, returns=None):
    def decorator(func):
        return View(func, method, accepts, returns)
    return decorator

class CorsPreflightView(object):

    def __init__(self, allowed_methods):
        self.allowed_methods = allowed_methods
        self.method = "OPTIONS"

    def __call__(self, req):
        origin = req.headers.get("Origin", None)
        # No Origin?
        if origin == None:
            error = "Preflight CORS request must include Origin header"
            return Response(400, error, {})
        # Access-Control-Request-Method is not set or set wrongly?
        requested_method = req.headers.get("Access-Control-Request-Method", None)
        if requested_method not in self.allowed_methods:
            error = "Access-Control-Request-Method header must be set to "
            error += " or ".join(self.allowed_methods)
            return Response(400, error, {})
        # Everything is good, make response
        res_headers = {}
        res_headers["Access-Control-Allow-Origin"] = origin
        res_headers["Access-Control-Allow-Methods"] = ",".join(self.allowed_methods)
        # Allow all requested headers
        allow_headers = req.headers.get('Access-Control-Request-Headers', None)
        if allow_headers != None:
            res_headers["Access-Control-Allow-Headers"] = allow_headers
        return Response(200, "", res_headers)

class UrlRule(object):

    def __init__(self, url, name, view):
        self.name = name
        self.url = url
        self.view = view


