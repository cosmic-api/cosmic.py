from __future__ import unicode_literals

import json
from werkzeug.local import LocalProxy, LocalStack
from teleport import Box, ValidationError

from .exceptions import *
from .tools import string_to_json

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

