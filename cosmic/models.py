import sys

from collections import OrderedDict

from werkzeug.local import LocalStack, LocalProxy
from flask.ctx import _AppCtxGlobals

from .types import *

from teleport import BasicWrapper, ParametrizedWrapper



class BaseModel(object):

    properties = []
    methods = []
    query_fields = []
    list_metadata = []
    links = []

    def __init__(self, **kwargs):
        self.id = kwargs.pop('id', None)
        self._representation = kwargs
        if self.id is not None and not kwargs:
            self._representation = None
        else:
            self._representation = kwargs

    @classmethod
    def validate_patch(cls, datum):
        pass

    def _force_representation(self):
        if self._representation is None:
            self._representation = self.__class__.get_by_id(self.id)

    def __getitem__(self, name):
        self._force_representation()
        return self._representation[name]

    def __contains__(self, name):
        self._force_representation()
        return name in self._representation



class Cosmos(object):

    def __init__(self):
        self.apis = {}
        self.g = _AppCtxGlobals()

    def clone(self):
        c = Cosmos()
        c.apis = dict(self.apis.items())
        return c

    def M(self, name):
        api_name, model_name = name.split('.', 1)
        return self.apis[api_name]._models[model_name]

    def __enter__(self):
        _ctx_stack.push(self)

    def __exit__(self, *args, **kwargs):
        _ctx_stack.pop()


_ctx_stack = LocalStack()



def M(name):
    from cosmic import cosmos
    return LocalProxy(lambda: cosmos.M(name)) 
