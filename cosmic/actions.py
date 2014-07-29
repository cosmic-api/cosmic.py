from __future__ import unicode_literals

from teleport import BasicWrapper

from .types import *


class Action(object):

    def __init__(self, accepts=None, returns=None, doc=None):
        self.accepts = accepts
        self.returns = returns
        self.doc = doc

    def __call__(self, *args, **kwargs):
        if hasattr(self, "func"):
            return self.func(*args, **kwargs)
        return self.endpoint(*args, **kwargs)

