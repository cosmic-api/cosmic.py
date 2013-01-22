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
    """A simplified representation of an HTTP request.

    :param string method: HTTP method
    :param string body: Request body
    :param dict headers: HTTP headers
    """
    def __init__(self, method, body, headers):
        self.method = method
        self.headers = headers
        self.body = body

class JSONRequest(Request):
    """If the passed in :class:`~apio.http.Request` validates, the
    resulting :class:`JSONRequest` will have a *payload* attribute,
    storing a :class:`~apio.tools.JSONPayload` object or ``None`` if
    the request body was empty.

    :param req: :class:`~apio.http.Request`
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
    """A simplified representation of an HTTP response.

    :param int code: HTTP status code
    :param string body: Response body
    :param dict headers: HTTP headers
    """
    def __init__(self, code, body="", headers={}):
        self.code = code
        self.body = body
        self.headers = headers

class View(object):
    """An HTTP request handler.

    :param function func: A function that takes a
        :class:`~apio.tools.JSONPayload` and returns a
        :class:`~apio.http.Response`. This function may raise an
        :class:`~apio.exceptions.APIError`,
        :class:`~apio.exceptions.ValidationError` or an
        :class:`~apio.exceptions.AuthenticationError`. Any other exception will
        result in 500 Internal Server Error response.
    :param string method: HTTP method that the view will respond to
    :param dict accepts: A JSON schema for validating *func* input
    :param dict returns: A JSON schema for validating *func* output
    """
    def __init__(self, func, method, accepts=None, returns=None):
        self.func = func
        self.method = method
        self.accepts = accepts
        self.returns = returns

    def __call__(self, req, debug=False):
        """Turns a :class:`~apio.http.Request` into a
        :class:`~apio.http.Response`.

        :param bool debug: If ``True``, an unhandled error in *func* will
            result in a crash and a stack trace.
        """
        res = Response(200)
        # Necessary for CORS
        if "Origin" in req.headers:
            res.headers["Access-Control-Allow-Origin"] = req.headers["Origin"]
        # Catch ClientErrors and APIErrors and turn them into Responses
        try:
            # Validate request
            try:
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

def make_view(method, accepts=None, returns=None):
    """A decorator for creating views more conveniently.

    .. code::

        >>> from apio.http import make_view
        >>> @make_view("POST", None, {"type": "int"})
        ... def number(payload):
        ...     return 42
        ...
        >>> number
        <apio.http.View object at 0x110ed50>

    """

    def decorator(func):
        return View(func, method, accepts, returns)
    return decorator

class CorsPreflightView(object):
    """An object that acts like a :class:`~apio.http.View` but performs a very
    specific function: handles `CORS
    <http://en.wikipedia.org/wiki/Cross-origin_resource_sharing>`_ preflight
    requests.

    :param list allowed_methods: A list of HTTP methods that will be declared
        as allowed for the URL where this view will be registered
    """
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
    """Represents the relationship between a URL and a
    :class:`~apio.http.View`. Your :class:`~apio.api.API` will be represented
    as a list of URL rules in order to get served.

    :param string URL: The URL which is mapped to the *view*
    :param string name: Endpoint name, necessary for Flask
    :param View view: When the client visits the URL, the *view* will handle
        her request.
    """

    def __init__(self, url, name, view):
        self.name = name
        self.url = url
        self.view = view


