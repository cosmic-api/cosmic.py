import sys

from collections import OrderedDict

from werkzeug.local import LocalStack, LocalProxy
from flask.ctx import _AppCtxGlobals

from .tools import GetterNamespace, validate_underscore_identifier

from .types import *

from teleport import BasicWrapper, ParametrizedWrapper


def prep_model(model_cls):
    from .http import CreateEndpoint, GetListEndpoint, GetByIdEndpoint, UpdateEndpoint, DeleteEndpoint

    link_names = set(dict(model_cls.links).keys())
    field_names = set(dict(model_cls.properties).keys())

    if link_names & field_names:
        raise SpecError("Model cannot contain a field and link with the same name: %s" % model_cls.__name__)

    for name in link_names | field_names:
        validate_underscore_identifier(name)

    if 'id' in link_names | field_names:
        raise SpecError("'id' is a reserved name.")

    model_cls._list_poster = CreateEndpoint(model_cls)
    model_cls._list_getter = GetListEndpoint(model_cls)
    model_cls._model_getter = GetByIdEndpoint(model_cls)
    model_cls._model_putter = UpdateEndpoint(model_cls)
    model_cls._model_deleter = DeleteEndpoint(model_cls)

    model_cls.schema = Representation(model_cls)
    # Make name visible through LocalProxy
    model_cls._name = model_cls.__name__




class BaseModel(object):
    """A data type definition attached to an API."""
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

    @classmethod
    def create(cls, **rep):
        raise NotImplementedError()

    @classmethod
    def update(cls, id, **rep):
        raise NotImplementedError()

    def _get_item(self, name):
        if name in self._patch:
            return self._patch[name]
        if self._representation is None:
            if self.id is None:
                return None
            i = self.__class__.get_by_id(self.id)
            self._representation = i._representation
        return self._representation.get(name, None)

    def _set_item(self, name, value):
        if value is not None:
            self._patch[name] = value
        else:
            del self._patch[name]

    def __getattr__(self, name):
        if name in OrderedDict(self.properties + self.links).keys():
            return self._get_item(name)
        else:
            raise AttributeError()

    def __setattr__(self, name, value):
        if name in OrderedDict(self.properties + self.links).keys():
            return self._set_item(name, value)
        else:
            super(BaseModel, self).__setattr__(name, value)




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
