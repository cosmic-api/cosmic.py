import sys

from collections import OrderedDict

from werkzeug.local import LocalStack

from teleport import *
from .exceptions import ModelNotFound
from .tools import GetterNamespace



class ModelSerializer(BasicWrapper):
    type_name = "cosmic.Model"

    schema = Struct([
        required("name", String),
        optional("data_schema", Schema),
        required("links", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ])))
    ])

    @staticmethod
    def assemble(datum):
        # Take a schema and name and turn them into a model class
        class M(Model):
            data_schema = datum["data_schema"]
            links = datum["links"]
        M.__name__ = str(datum["name"])
        prep_model(M)
        return M

    @staticmethod
    def disassemble(datum):
        return {
            "name": datum.__name__,
            "data_schema": datum.data_schema,
            "links": datum.links if hasattr(datum, "links") else OrderedDict()
        }


def prep_model(model_cls):
    link_schema = Struct([
        required("href", String)
    ])
    links = [
        ("self", {
            "required": True,
            "schema": link_schema
        })
    ]
    for name, link in model_cls.links.items():
        links.append((name, {
            "required": link["required"],
            "schema": link_schema
        }))
    model_cls.schema = Struct([
        required("_links", Struct(links)),
        required("_data", model_cls.data_schema)
    ])


class Model(BasicWrapper):
    """A data type definition attached to an API."""
    query_fields = None
    links = OrderedDict()

    def __init__(self, data):
        self.data = data

    @property
    def href(self):
        return "/%s/%s" % (self.__class__.__name__, self.id)

    @classmethod
    def assemble(cls, datum):
        cls.validate(datum["_data"])
        inst = cls(datum["_data"])
        inst.__lazy_links = {}
        for name, link in datum["_links"].items():
            url = link["href"]
            parts = url.split('/')
            id = parts[-1]

            if name == "self":
                model_cls = cls
                inst.id = id
            else:
                model_cls = cls.links[name]["schema"]
                inst.__lazy_links[name] = lambda: model_cls.get_by_id(int(id))

            if parts[-2] != model_cls.__name__:
                raise ValidationError("Invalid url for %s link: %s" % (model_cls.__name__, url))

        return inst

    @classmethod
    def disassemble(cls, datum):
        links = OrderedDict()
        links["self"] = {"href": datum.href}
        for name, link in cls.links.items():
            value = getattr(datum, name)
            if value != None:
                links[name] = {"href": value.href}
        return {
            "_data": datum.data,
            "_links": links
        }

    def __getattr__(self, name):
        if name not in self.links.keys():
            raise AttributeError()
        if name in self.__lazy_links.keys():
            value = self.__lazy_links[name]()
            setattr(self, name, value)
            return value
        else:
            return None


    @classmethod
    def validate(cls, datum):
        pass

    @classmethod
    def get_list(cls, **kwargs):
        raise NotImplementedError()

    @classmethod
    def get_by_id(cls, id):
        from .http import ModelGetterCallable
        return ModelGetterCallable(cls)(id)


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

