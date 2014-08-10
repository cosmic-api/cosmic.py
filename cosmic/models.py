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




class BaseModel(BasicWrapper):
    """A data type definition attached to an API."""
    methods = []
    query_fields = []
    list_metadata = []
    links = []

    def __init__(self, **kwargs):
        self.id = kwargs.pop('id', None)
        if kwargs:
            self._remote_representation = kwargs
        else:
            self._remote_representation = None
        self._local_representation = {}

    @property
    def href(self):
        return "/%s/%s" % (self.__class__.__name__, self.id)

    @classmethod
    def assemble(cls, datum):
        (id, rep) = datum

        inst = cls()
        inst.id = id
        inst._remote_representation = rep

        cls.validate(rep)

        return inst

    @classmethod
    def id_from_url(cls, url):
        parts = url.split('/')
        if parts[-2] != cls.__name__:
            raise ValidationError("Invalid url for %s link: %s" % (cls.__name__, url))
        return parts[-1]

    @classmethod
    def disassemble(cls, datum):
        rep = {}
        for name, link in OrderedDict(cls.links).items():
            value = datum._get_item(name)
            if value != None:
                rep[name] = value
        for name in OrderedDict(cls.properties).keys():
            value = datum._get_item(name)
            if value != None:
                rep[name] = value

        return (datum.id, rep)

    def _get_item(self, name):
        if name in self._local_representation:
            return self._local_representation[name]
        if self._remote_representation is None:
            i = self.__class__.get_by_id(self.id)
            self._remote_representation = i._remote_representation
        return self._remote_representation.get(name, None)

    def _set_item(self, name, value):
        if value is not None:
            self._local_representation[name] = value
        else:
            del self._local_representation[name]

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

    @classmethod
    def validate(cls, datum):
        pass



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


# Teleport reads param_schema, we don't want that to trigger local resolution
class LocalProxyHack(LocalProxy):
    param_schema = None


def M(name):
    from cosmic import cosmos
    return LocalProxyHack(lambda: cosmos.M(name)) 
