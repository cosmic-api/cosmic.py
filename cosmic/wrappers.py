from flask.wrappers import Request as RequestBase
from werkzeug.utils import cached_property

from .tools import json_to_string, string_to_json
from .exceptions import *

class Request(RequestBase):

    def _get_json_payload(self):
        if self.method != "GET" and self.content_type != "application/json":
            raise SpecError('Content-Type must be "application/json" got %s instead' % self.content_type)
        try:
            return string_to_json(self.data)
        except ValueError:
            # Let's be more specific
            raise JSONParseError()

    @cached_property
    def json_payload(self):
        return self._get_json_payload()
