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
            links = datum["links"]
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
    model_cls.schema = Struct(props)


class Model(BasicWrapper):
    """A data type definition attached to an API."""
    query_fields = []
    links = []
    _representation_data = None
    _representation_links = None
    id = None

    def __init__(self, data=None):
        if data:
            self._representation_data = data

    @property
    def href(self):
        return "/%s/%s" % (self.__class__.__name__, self.id)

    @classmethod
    def assemble(cls, datum):
        inst = cls()
        inst._fill_out(datum)
        return inst

    @staticmethod
    def id_from_url(url, model_cls):
        parts = url.split('/')
        if parts[-2] != model_cls.__name__:
            raise ValidationError("Invalid url for %s link: %s" % (model_cls.__name__, url))
        return parts[-1]

    def _fill_out(self, datum):
        links = datum.pop("_links", {})
        self.validate(datum)
        self._representation_links = {}
        for name in OrderedDict(self.links).keys():
            if name in links:
                url = links[name]["href"]
                model_cls = OrderedDict(self.links)[name]["schema"]
                id = Model.id_from_url(url, model_cls)
                self._set_link(name, model_cls.get_by_id(id))
            else:
                self._set_link(name, None)
        self._representation_data = {}
        for name in OrderedDict(self.properties).keys():
            if name in datum:
                self._set_data(name, datum[name])
            else:
                self._set_data(name, None)
        if "self" in links:
            id = Model.id_from_url(links["self"]["href"], self.__class__)
            if self.id == None:
                self.id = id
            elif self.id != id:
                raise ValidationError("Expected id: %s, actual: %s" % (self.id, id))

    @classmethod
    def disassemble(cls, datum):
        links = OrderedDict()
        if hasattr(datum, "id"):
            links["self"] = {"href": datum.href}
        for name, link in OrderedDict(cls.links).items():
            value = datum._get_link(name)
            if value != None:
                links[name] = {"href": value.href}
        d = {}
        if links:
            d["_links"] = links
        for name in OrderedDict(cls.properties).keys():
            value = datum._get_data(name)
            if value != None:
                d[name] = value
        return d

    def _get_data(self, name):
        if self._representation_data == None:
            if self.id:
                self._force()
            else:
                self._fill_out({})
        return self._representation_data.get(name, None)

    def _get_link(self, name):
        if self._representation_links == None:
            if self.id:
                self._force()
            else:
                self._fill_out({})
        return self._representation_links.get(name, None)

    def _set_data(self, name, value):
        if self._representation_data == None:
            if self.id:
                self._force()
            else:
                self._fill_out({})
        if value == None and name in self._representation_data:
            del self._representation_data[name]
        self._representation_data[name] = value

    def _set_link(self, name, value):
        if self._representation_links == None:
            if self.id:
                self._force()
            else:
                self._fill_out({})
        if value == None and name in self._representation_links:
            del self._representation_links[name]
        self._representation_links[name] = value

    def __getattr__(self, name):
        if name in OrderedDict(self.links).keys():
            return self._get_link(name)
        elif name in OrderedDict(self.properties).keys():
            return self._get_data(name)
        else:
            raise AttributeError()

    def __setattr__(self, name, value):
        if name in OrderedDict(self.links).keys():
            return self._set_link(name, value)
        elif name in OrderedDict(self.properties).keys():
            return self._set_data(name, value)
        else:
            super(Model, self).__setattr__(name, value)

    def save(self):
        from .http import ModelPutterCallable
        return ModelPutterCallable(self.__class__)(self)

    def delete(self):
        from .http import ModelDeleterCallable
        return ModelDeleterCallable(self.__class__)(self)

    @classmethod
    def validate(cls, datum):
        pass

    @classmethod
    def get_list(cls, **query):
        from .http import ListGetterCallable
        return ListGetterCallable(cls)(**query)

    @classmethod
    def get_by_id(cls, id):
        inst = cls()
        inst.id = id
        return inst

    def _force(self):
        from .http import ModelGetterCallable
        self._fill_out(ModelGetterCallable(self.__class__)(self.id))



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

