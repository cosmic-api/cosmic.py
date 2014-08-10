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

        if self.id is None:
            self._representation = None
            self._patch = kwargs
        else:
            if not kwargs:
                kwargs = None
            self._representation = kwargs
            self._patch = {}

    @property
    def href(self):
        return "/%s/%s" % (self.__class__.__name__, self.id)

    @classmethod
    def assemble(cls, datum):
        (id, rep) = datum

        inst = cls()
        inst.id = id
        inst._representation = rep

        cls.validate(rep)

        return inst

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
    def create(cls, **rep):
        raise NotImplementedError()

    @classmethod
    def update(cls, id, **rep):
        raise NotImplementedError()

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
