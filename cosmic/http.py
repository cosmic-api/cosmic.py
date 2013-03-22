from __future__ import unicode_literals

import json

from cosmic.exceptions import *
from cosmic.tools import normalize, normalize_schema, fetch_model
from cosmic.models import JSONData

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
    """If the passed in :class:`~cosmic.http.Request` *req* validates, the
    resulting :class:`JSONRequest` will have a *payload* attribute, storing a
    :class:`~cosmic.models.JSONData` object or ``None`` if the request body
    was empty. For a non-GET request, Content-Type has to be
    ``application/json``.

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
            self.payload = JSONData.from_string(req.body)
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
        :class:`~cosmic.models.JSONData` and returns a
        :class:`~cosmic.models.JSONData`.
    :param string method: HTTP method that the view will respond to
    """
    def __init__(self, func, method):
        self.func = func
        self.method = method

    def __call__(self, req, debug=False):
        """Uses *func* to turn a :class:`~cosmic.http.Request` into a
        :class:`~cosmic.http.Response`.

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
                data = self.func(req.payload)
                if data != None:
                    res.body = json.dumps(data.data)
                return res
            except HttpError:
                raise
            except JSONParseError:
                raise ClientError("Invalid JSON")
            except SpecError as err:
                raise ClientError(err.args[0])
            except ValidationError as e:
                raise ClientError(e.print_json())
            # Any other exception should be handled gracefully
            except:
                if debug:
                    raise
                raise APIError("Internal Server Error")
        except HttpError as err:
            return err.get_response()

def make_view(method):
    """A decorator for creating views more conveniently. Passes the function
    below, and the decorator arguments into the :class:`~cosmic.http.View`
    constructor.

    .. code::

        >>> from cosmic.http import make_view
        >>> @make_view("POST")
        ... def number(payload):
        ...     return JSONData(42)
        ...
        >>> number
        <cosmic.http.View object at 0x110ed50>

    """

    def decorator(func):
        return View(func, method)
    return decorator

class CorsPreflightView(object):
    """An object that acts like a :class:`~cosmic.http.View` but performs a very
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
    :class:`~cosmic.http.View`. Your :class:`~cosmic.api.API` will be represented
    as a list of URL rules.

    :param string url: The URL which is mapped to the *view*
    :param string name: Endpoint name, necessary for Flask
    :param View view: When the client visits the URL, the *view* will handle
        her request.
    """

    def __init__(self, url, name, view):
        self.name = name
        self.url = url
        self.view = view


