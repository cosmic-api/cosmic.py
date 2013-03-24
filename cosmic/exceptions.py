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

class ValidationError(Exception):
    """Raised by the model system. Stores the location of the error in the
    JSON document relative to its root for a more useful stack trace.

    First parameter is the error *message*, second optional parameter is the
    object that failed validation.
    """

    def __init__(self, message, *args):
        super(ValidationError, self).__init__(message)
        self.stack = []
        # Just the message or was there also an object passed in?
        self.has_obj = len(args) > 0
        if self.has_obj:
            self.obj = args[0]

    def _print_with_format(self, func):
        # Returns the full error message with the representation
        # of its literals determined by the passed in function.
        ret = ""
        # If there is a stack, preface the message with a location
        if self.stack:
            stack = ""
            for item in reversed(self.stack):
                stack += func([item])
            ret += "Item at %s " % stack
        # Main message
        ret += self.message
        # If an object was passed in, represent it at the end
        if self.has_obj:
            ret += ": %s" % func(self.obj)
        return ret

    def __str__(self):
        return self._print_with_format(repr)

    def print_json(self):
        """Print the same message as the one you would find in a
        console stack trace, but using JSON to output all the language
        literals. This representation is used for sending error
        messages over the wire.
        """
        return self._print_with_format(json.dumps)

class UnicodeDecodeValidationError(ValidationError):
    """A subclass of :exc:`~cosmic.exceptions.ValidationError` raised
    in place of a :exc:`UnicodeDecodeError`.
    """
