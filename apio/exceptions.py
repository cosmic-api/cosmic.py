from __future__ import unicode_literals

class APIError(Exception):
    def __init__(self, message, http_code=500):
        self.args = [message]
        self.http_code = http_code

class SpecError(Exception):
    pass

class InvalidCallError(Exception):
    pass

class AuthenticationError(Exception):
    pass

class ValidationError(Exception):
    def __init__(self, message, stack=None):
        super(ValidationError, self).__init__(message)
        if stack == None:
            self.stack = []
        else:
            self.stack = stack

class UnicodeDecodeValidationError(ValidationError):
    pass
