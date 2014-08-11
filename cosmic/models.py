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

        if self.id is None:
            self._representation = None
            self._patch = kwargs
        else:
            if not kwargs:
                kwargs = None
            self._representation = kwargs
            self._patch = {}

    @classmethod
    def from_json(cls, datum):
        (id, rep) = Representation(cls).from_json(datum)
        cls.validate(rep)
        return cls(id=id, **rep)

    @classmethod
    def to_json(cls, datum):
        rep = datum.get_patch()
        return Representation(cls).to_json((datum.id, rep))

    def get_patch(self):
        ret = {}
        if self._representation is not None:
            ret.update(self._representation)
        ret.update(self._patch)
        return ret

    def save(self):
        self.__class__.validate(self.get_patch())
        if self.id:
            (id, rep) = self.__class__.update(self.id, **self.get_patch())
            self._representation = rep
            self._patch = {}
        else:
            (id, rep) = self.__class__.create(**self.get_patch())
            self.id = id
            self._representation = rep
            self._patch = {}

    @classmethod
    def validate(cls, datum):
        pass

    def __getitem__(self, name):
        if name not in OrderedDict(self.properties + self.links).keys():
            raise KeyError()
        if name in self._patch:
            return self._patch[name]
        if self._representation is None:
            if self.id is None:
                return None
            i = self.__class__.get_by_id(self.id)
            self._representation = i._representation
        return self._representation.get(name, None)

    def __setitem__(self, name, value):
        if name not in OrderedDict(self.properties + self.links).keys():
            super(BaseModel, self).__setattr__(name, value)
        if value is not None:
            self._patch[name] = value
        else:
            del self._patch[name]




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
