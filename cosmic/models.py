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
        optional("schema", Schema),
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
            schema = datum["schema"]
            links = datum["links"]
        M.__name__ = str(datum["name"])
        return M

    @staticmethod
    def disassemble(datum):
        return {
            "name": datum.__name__,
            "schema": datum.schema,
            "links": datum.links if hasattr(datum, "links") else OrderedDict()
        }


class HALResource(ParametrizedWrapper):

    def __init__(self, param):
        self.param = param
        self.schema = Struct([
            required("_links", Map(Struct([
                required("href", String)
            ]))),
            required("_data", param)
        ])



class Model(BasicWrapper):
    """A data type definition attached to an API."""
    collection = None
    query_fields = None

    def __init__(self, data):
        self.data = data

    @classmethod
    def from_json(cls, datum):
        datum = HALResource(cls.schema).from_json(datum)
        return cls.assemble(datum)

    @classmethod
    def to_json(cls, datum):
        datum = cls.disassemble(datum)
        return HALResource(cls.schema).to_json(datum)

    @classmethod
    def assemble(cls, datum):
        cls.validate(datum["_data"])
        inst = cls(datum)
        inst.__lazy_links = {}
        for name, link in datum["_links"].items():
            url = link["href"]
            if name not in cls.links.keys():
                raise ValidationError("Unexpected link: %s" % name)
            model_cls = cls.links[name]["schema"]
            parts = url.split('/')
            if parts[-2] != model_cls.__name__:
                raise ValidationError("Invalid url for %s link: %s" % (model_cls.__name__, url))
            id = parts[-1]
            inst.__lazy_links[name] = lambda: model_cls.get_by_id(int(id))
        return inst

    def __getattr__(self, name):
        if name in self.__lazy_links.keys():
            value = self.__lazy_links[name]()
            setattr(self, name, value)
            return value

    @classmethod
    def validate(cls, datum):
        pass

    @classmethod
    def disassemble(cls, datum):
        return datum.data

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

