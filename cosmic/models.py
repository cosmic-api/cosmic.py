import sys

from collections import OrderedDict

from werkzeug.local import LocalStack, LocalProxy
from flask.ctx import _AppCtxGlobals

from teleport import *
from .exceptions import ModelNotFound
from .tools import GetterNamespace, validate_underscore_identifier


def prep_model(model_cls):
    from .http import ListPoster, ListGetter, ModelGetter, ModelPutter, ModelDeleter

    link_schema = Struct([
        required("href", String)
    ])
    links = [
        ("self", {
            "required": False,
            "schema": link_schema
        })
    ]
    link_names = set()
    field_names = set()
    for name, link in model_cls.links:
        validate_underscore_identifier(name)
        link_names.add(name)
        links.append((name, {
            "required": link["required"],
            "schema": link_schema
        }))
    props = [
        optional("_links", Struct(links)),
    ]
    for name, field in model_cls.properties:
        validate_underscore_identifier(name)
        field_names.add(name)
        props.append((name, field))
    if link_names & field_names:
        raise SpecError("Model cannot contain a field and link with the same name: %s" % model_cls.__name__)
    if 'id' in link_names | field_names:
        raise SpecError("'id' is a reserved name.")

    model_cls._list_poster = ListPoster(model_cls)
    model_cls._list_getter = ListGetter(model_cls)
    model_cls._model_getter = ModelGetter(model_cls)
    model_cls._model_putter = ModelPutter(model_cls)
    model_cls._model_deleter = ModelDeleter(model_cls)

    model_cls.schema = Struct(props)


class Model(BasicWrapper):
    """A data type definition attached to an API."""
    query_fields = []
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
        inst = cls()

        rep = {}
        links = datum.pop("_links", {})
        for name in OrderedDict(cls.links).keys():
            if name in links:
                url = links[name]["href"]
                model_cls = OrderedDict(cls.links)[name]["schema"]
                id = model_cls.id_from_url(url)
                rep[name] = model_cls(id=id)
            else:
                rep[name] = None
        for name in OrderedDict(cls.properties).keys():
            if name in datum:
                rep[name] = datum[name]
            else:
                rep[name] = None
        if "self" in links:
            id = cls.id_from_url(links["self"]["href"])
        else:
            id = None
        cls.validate(rep)

        inst._remote_representation = rep
        inst.id = id

        return inst

    @classmethod
    def id_from_url(cls, url):
        parts = url.split('/')
        if parts[-2] != cls.__name__:
            raise ValidationError("Invalid url for %s link: %s" % (cls.__name__, url))
        return parts[-1]

    @classmethod
    def disassemble(cls, datum):
        links = OrderedDict()
        if datum.id:
            links["self"] = {"href": datum.href}
        for name, link in OrderedDict(cls.links).items():
            value = datum._get_item(name)
            if value != None:
                links[name] = {"href": value.href}
        d = {}
        if links:
            d["_links"] = links
        for name in OrderedDict(cls.properties).keys():
            value = datum._get_item(name)
            if value != None:
                d[name] = value
        return d

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
            super(Model, self).__setattr__(name, value)

    @classmethod
    def validate(cls, datum):
        pass



class RemoteModel(Model):

    def save(self):
        if self.id:
            inst = self.__class__._model_putter(self.id, self)
        else:
            inst = self.__class__._list_poster(self)
            self.id = inst.id
        self._remote_representation = inst._remote_representation
        self._local_representation = {}

    def delete(self):
        return self.__class__._model_deleter(self)

    @classmethod
    def get_list(cls, **query):
        return cls._list_getter(**query)

    @classmethod
    def get_by_id(cls, id):
        return cls._model_getter(id)


class Cosmos(TypeMap):

    def __init__(self):
        self.apis = {}
        self.g = _AppCtxGlobals()

    def M(self, name):
        api_name, model_name = name.split('.', 1)
        return self.apis[api_name]._models[model_name]

    def __enter__(self):
        _ctx_stack.push(self)
        super(Cosmos, self).__enter__()

    def __exit__(self, *args, **kwargs):
        _ctx_stack.pop()
        super(Cosmos, self).__exit__(*args, **kwargs)

    def __getitem__(self, name):
        from api import API
        from actions import Function
        if name == "cosmic.API":
            return (API, None,)
        elif name == "cosmic.Function":
            return (Function, None,)
        elif '.' in name:
            return (M(name), None,)
        else:
            return BUILTIN_TYPES[name]

_ctx_stack = LocalStack()

def M(name):
    from cosmic import cosmos
    return LocalProxy(lambda: cosmos.M(name))

