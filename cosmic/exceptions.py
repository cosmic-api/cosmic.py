from __future__ import unicode_literals

from flask import make_response

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
        """Create a response object with the error code and message.
        """
        body = json.dumps({"error": self.message})
        return make_response(body, self.http_code, {})

class ModelNotFound(Exception):
    pass

class SpecError(Exception):
    pass

