from __future__ import unicode_literals

import json

class JSONParseError(Exception):
    """Raised in place of the generic :exc:`ValueError`"""

class HttpError(Exception):
    """Raised to interrupt an API function and return an HTTP error code to
    the client.
    """
    def __init__(self, message):
        self.message = message
        self.args = [message]
    def get_response(self):
        """Create a :class:`~cosmic.http.Response` object with the error code
        and message.
        """
        from cosmic.http import Response
        body = json.dumps({"error": self.message})
        return Response(self.http_code, body, {})

class APIError(HttpError):
    """An :class:`~cosmic.exceptions.HttpError` with default HTTP code 500.
    """
    http_code = 500

class ClientError(HttpError):
    """An :class:`~cosmic.exceptions.HttpError` with default HTTP code 400.
    """
    http_code = 400

class AuthenticationError(ClientError):
    """A :class:`~cosmic.exceptions.ClientError` with 401 HTTP code and
    "Authentication failed" message.
    """
    http_code = 401
    message = "Authentication failed"
    def __init__(self):
        pass

class SpecError(Exception):
    pass

