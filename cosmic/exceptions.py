from __future__ import unicode_literals

import json

class JSONParseError(Exception):
    pass

class HttpError(Exception):
    def __init__(self, message, http_code=None):
        self.message = message
        self.args = [message]
        if http_code:
            self.http_code = http_code
    def get_response(self):
        from cosmic.http import Response
        body = json.dumps({"error": self.message})
        return Response(self.http_code, body, {})

class APIError(HttpError):
    http_code = 500

class ClientError(HttpError):
    http_code = 400

class AuthenticationError(ClientError):
    http_code = 401
    message = "Authentication failed"
    def __init__(self):
        pass

class SpecError(Exception):
    pass

class ValidationError(Exception):

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
    pass
