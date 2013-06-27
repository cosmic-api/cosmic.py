from teleport import Box

from werkzeug.exceptions import MethodNotAllowed

class Document(object):
    methods = ["GET", "PUT", "DELETE"]
    schema = None

    def _get(self, payload):
        "returns representation of doc and links to other docs and sets"
        return Box(self.schema.to_json(self.get()))

    def _put(self, payload):
        "updates (overwrites) it"
        new = self.schema.from_json(payload)
        return self.schema.to_json(self.put(new))

    def _delete(self, payload):
        return self.delete()

"""
class Collection(object):
    methods = ["GET", "POST"]
    document = None
    def get(self):
        return "page of model instances with links: next, prev etc."
    def post(self):
        return "create a new model instance"
"""

