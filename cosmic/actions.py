from __future__ import unicode_literals

from teleport import BasicWrapper

from .types import *


class Action(object):

    def __init__(self, accepts=None, returns=None, doc=None):
        self.accepts = accepts
        self.returns = returns
        self.doc = doc

