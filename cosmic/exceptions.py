from __future__ import unicode_literals

class JSONParseError(Exception):
    """Raised in place of the generic :exc:`ValueError`"""

class ModelNotFound(Exception):
    pass

class SpecError(Exception):
    pass
