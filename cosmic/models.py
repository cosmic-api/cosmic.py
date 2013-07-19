import sys

from collections import OrderedDict

from werkzeug.local import LocalStack

from teleport import *
from .exceptions import ModelNotFound
from .tools import GetterNamespace, validate_underscore_identifier



class ModelSerializer(BasicWrapper):
    type_name = "cosmic.Model"

    schema = Struct([
        required("name", String),
        optional("data_schema", Schema),
        required("links", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ]))),
        required("query_fields", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ])))
    ])

    @staticmethod
    def assemble(datum):
        # Take a schema and name and turn them into a model class
        class M(Model):
            properties = datum["data_schema"].param.items()
            query_fields = datum["query_fields"]
            links = datum["links"].items()
        M.__name__ = str(datum["name"])
        prep_model(M)
        return M

    @staticmethod
    def disassemble(datum):
        return {
            "name": datum.__name__,
            "data_schema": Struct(datum.properties),
            "links": OrderedDict(datum.links if hasattr(datum, "links") else []),
            "query_fields": OrderedDict(datum.query_fields if hasattr(datum, "query_fields") else [])
        }


def prep_model(model_cls):
    from .http import ListPoster, ListGetter, ModelGetter, ModelPutter, ModelDeleter

    link_schema = Struct([
        required("href", String)
    ])
    links = [
        ("self", {
            "required": True,
            "schema": link_schema
        })
    ]
    link_names = set()
    field_names = set()
    for name, link in OrderedDict(model_cls.links).items():
        validate_underscore_identifier(name)
        link_names.add(name)
        links.append((name, {
            "required": link["required"],
            "schema": link_schema
        }))
    props = [
        optional("_links", Struct(links)),
    ]
    for name, field in OrderedDict(model_cls.properties).items():
        validate_underscore_identifier(name)
        field_names.add(name)
        props.append((name, field))
    if link_names & field_names:
        raise SpecError("Model cannot contain a field and link with the same name: %s" % model_cls.__name__)

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

    def __init__(self, data=None):
        self.id = None
        if data:
            _, self._representation = self.__class__._fill_out(data)
        else:
            self._representation = None

    @property
    def href(self):
        return "/%s/%s" % (self.__class__.__name__, self.id)

    @classmethod
    def assemble(cls, datum):
        inst = cls()
        inst.id, inst._representation = cls._fill_out(datum)
        return inst

    @classmethod
    def id_from_url(cls, url):
        parts = url.split('/')
        if parts[-2] != cls.__name__:
            raise ValidationError("Invalid url for %s link: %s" % (cls.__name__, url))
        return parts[-1]

    @classmethod
    def _fill_out(cls, datum):
        rep = {}
        links = datum.pop("_links", {})
        for name in OrderedDict(cls.links).keys():
            if name in links:
                url = links[name]["href"]
                model_cls = OrderedDict(cls.links)[name]["schema"]
                id = model_cls.id_from_url(url)
                rep[name] = model_cls.get_by_id(id)
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
        return (id, rep)

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
        if self._representation == None:
            if self.id:
                self._force()
            else:
                self.id, self._representation = self.__class__._fill_out({})
        return self._representation.get(name, None)

    def _set_item(self, name, value):
        if self._representation == None:
            if self.id:
                self._force()
            else:
                self.id, self._representation = self.__class__._fill_out({})
        self._representation[name] = value

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

    def save(self):
        if self.id:
            return self.__class__._model_putter(self.id, self)
        else:
            self.id = self.__class__._list_poster(self)

    def delete(self):
        return self.__class__._model_deleter(self)

    @classmethod
    def validate(cls, datum):
        pass

    @classmethod
    def get_list(cls, **query):
        return cls._list_getter(**query)

    @classmethod
    def get_by_id(cls, id):
        inst = cls()
        inst.id = id
        return inst

    def _force(self):
        m = self.__class__._model_getter(self.id)
        self.__class__.validate(m)
        id, self._representation = self.__class__._fill_out(m)
        if self.id != id:
            raise ValidationError("Expected id: %s, actual: %s" % (self.id, id))



class LazyWrapper(object):
    _model_cls = None

    def __init__(self, type_name):
        self.type_name = type_name

    def from_json(self, datum):
        return self.model_cls.from_json(datum)

    def to_json(self, datum):
        return self.model_cls.to_json(datum)

    @property
    def model_cls(self):
        from . import cosmos
        if not self._model_cls:
            self._model_cls = cosmos.get_model(self.type_name)
        return self._model_cls


class Cosmos(TypeMap):

    def __init__(self):
        self.lazy_serializers = []
        self.apis = {}

    def force(self):
        for serializer in self.lazy_serializers:
            serializer._model_cls = self.get_model(serializer.type_name)
        self.lazy_serializers = []

    def get_model(self, name):
        api_name, model_name = name.split('.', 1)
        try:
            api = self.apis[api_name]
            model = api._models[model_name]
            return model
        except KeyError:
            raise ModelNotFound(name)

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
        elif name == "cosmic.Model":
            return (ModelSerializer, None,)
        elif name == "cosmic.Function":
            return (Function, None,)
        elif '.' in name:
            try:
                model_cls = self.get_model(name)
                return (model_cls, None,)
            except ModelNotFound:
                lazy_model = LazyWrapper(name)
                self.lazy_serializers.append(lazy_model)
                return (lazy_model, None,)
        else:
            return BUILTIN_TYPES[name]

_ctx_stack = LocalStack()
# If the stack is empty, use this global object
_global_cosmos = Cosmos()

