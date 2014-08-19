from __future__ import unicode_literals
import json
import inspect
from collections import OrderedDict

import requests
from teleport import BasicWrapper

from .models import BaseModel
from .tools import get_args, assert_is_compatible, \
    validate_underscore_identifier
from .types import *
from .http import ClientHook, CreateEndpoint, DeleteEndpoint, \
    GetByIdEndpoint, GetListEndpoint, UpdateEndpoint, ActionEndpoint
from .globals import cosmos
from . import MODEL_METHODS


class Object(object):
    pass


class APISpec(BasicWrapper):
    type_name = "cosmic.APISpec"

    schema = Struct([
        required("name", String),
        optional("homepage", String),
        required("actions", OrderedMap(Struct([
            optional("accepts", Schema),
            optional("returns", Schema),
            optional("doc", String)
        ]))),
        required("models", OrderedMap(Struct([
            required("properties", OrderedMap(Struct([
                required(u"schema", Schema),
                required(u"required", Boolean),
                optional(u"doc", String)
            ]))),
            required("links", OrderedMap(Struct([
                required(u"model", Model),
                required(u"required", Boolean),
                optional(u"doc", String)
            ]))),
            required("query_fields", OrderedMap(Struct([
                required(u"schema", Schema),
                required(u"required", Boolean),
                optional(u"doc", String)
            ]))),
            required("methods", Struct([
                required("get_by_id", Boolean),
                required("get_list", Boolean),
                required("create", Boolean),
                required("update", Boolean),
                required("delete", Boolean),
                ])),
            required("list_metadata", OrderedMap(Struct([
                required(u"schema", Schema),
                required(u"required", Boolean),
                optional(u"doc", String)
            ])))
        ])))
    ])


class API(object):
    """An instance of this class represents a Cosmic API, whether it's your
    own API being served or a third-party API being consumed. In the former
    case, the API object is instantiated by the constructor and is bound to a
    database ORM and other user-defined functions. In the latter case, it is
    instantiated by the :meth:`API.load` method and these functions are
    replaced by automatically generated HTTP calls.

    One of the primary goals of Cosmic is to make local and remote APIs behave
    as similarly as possible.

    :param name: The API name is required, and should be unique
    :param homepage: If you like, the API spec may include a link to your
        homepage
    """

    def __init__(self, name=None, homepage=None):
        self.api_spec = {
            "name": name,
            "homepage": homepage,
            "actions": OrderedDict(),
            "models": OrderedDict(),
        }
        self.client_hook = ClientHook()

        self.action_funcs = {}
        self.model_funcs = {}

        self._models = OrderedDict()

        self.models = Object()
        self.actions = Object()

        cosmos[self.name] = self

    @property
    def name(self):
        return self.api_spec['name']

    @name.setter
    def name(self, name):
        self.api_spec['name'] = name

    @property
    def homepage(self):
        return self.api_spec['homepage']

    @homepage.setter
    def homepage(self, name):
        self.api_spec['homepage'] = name

    def run(self, port=5000, **kwargs):
        """Simple way to run the API in development. Uses Werkzeug's
        :meth:`werkzeug.serving.run_simple` internally. See
        :ref:`guide-serving` for more options.
        """
        from werkzeug.serving import run_simple
        from .http import Server

        server = Server(self)
        run_simple('127.0.0.1', port, server.wsgi_app, **kwargs)

    def call_remote(self, endpoint_cls, endpoint_args, *args, **kwargs):
        return self.client_hook.call(endpoint_cls(*endpoint_args), *args,
                                     **kwargs)

    def to_json(self):
        return APISpec.to_json(self.api_spec)

    @classmethod
    def from_json(cls, datum):
        return cls.assemble_from_spec(APISpec.from_json(datum))

    @staticmethod
    def assemble_from_spec(datum):
        from functools import partial

        api = API(name=datum["name"], homepage=datum.get("homepage", None))
        api.api_spec = datum

        for name, action in datum["actions"].items():
            setattr(api.actions, name,
                    partial(api.call_remote, ActionEndpoint, [api, name]))

        for name, modeldef in datum["models"].items():
            class M(BaseModel):
                properties = modeldef["properties"].items()
                query_fields = modeldef["query_fields"].items()
                list_metadata = modeldef["list_metadata"].items()
                links = modeldef["links"].items()
                methods = filter(lambda m: modeldef["methods"][m],
                                 MODEL_METHODS)

            M.name = str(name)
            M.__name__ = M.name
            M.api = api

            M.create = staticmethod(
                partial(api.call_remote, CreateEndpoint, [api, name]))
            M.update = staticmethod(
                partial(api.call_remote, UpdateEndpoint, [api, name]))
            M.delete = staticmethod(
                partial(api.call_remote, DeleteEndpoint, [api, name]))
            M.get_list = staticmethod(
                partial(api.call_remote, GetListEndpoint, [api, name]))
            M.get_by_id = staticmethod(
                partial(api.call_remote, GetByIdEndpoint, [api, name]))

            api._validate_model(M)

            api._models[M.name] = M
            setattr(api.models, M.name, M)

        return api

    @staticmethod
    def load(url, verify=True):
        """Given a URL to a Cosmic API, fetch the API spec and build an API
        client:

        .. code:: python

            >>> planetarium = API.load("http://localhost:5000/spec.json") # doctest: +SKIP
            >>> planetarium.models.Sphere.get_by_id("0") # doctest: +SKIP
            {"name": "Earth"}

        :param url: The API spec url, including ``/spec.json``
        :rtype: :class:`API` instance
        """
        res = requests.get(url, verify=verify)
        api = API.from_json(res.json())
        # Set the API url to be the spec URL, minus the /spec.json
        api.client_hook.base_url = url[:-10]
        return api

    def action(self, accepts=None, returns=None):
        """A decorator for creating actions out of functions and registering
        them with the API.

        The *accepts* parameter is a schema that describes the input of the
        function, *returns* is a schema that describes the output of the
        function. The name of the function becomes the name of the action and
        the docstring serves as the action's documentation.

        Once registered, an action will become accessible as an attribute of
        the :data:`~cosmic.api.API.actions` object.

        .. code:: python

            >>> random = API("random")
            >>> @random.action(returns=Integer)
            ... def generate():
            ...     "Random enough"
            ...     return 9
            >>> random.actions.generate()
            9

        """

        def wrapper(func):
            name = unicode(func.__name__)
            validate_underscore_identifier(name)
            required, optional = get_args(func)

            if accepts:
                assert_is_compatible(accepts, required, optional)

            doc = inspect.getdoc(func)
            self.action_funcs[name] = func
            self.api_spec['actions'][name] = {
                "accepts": accepts,
                "returns": returns,
                "doc": doc,
            }

            setattr(self.actions, name, func)

            return func

        return wrapper

    def model(self, model_cls):
        """A decorator for registering a model with an API. The name of the
        model class is used as the name of the resulting model.

        .. code:: python

            >>> dictionary = API("dictionary")
            >>> @dictionary.model
            ... class Word(BaseModel):
            ...    properties = [
            ...        required("text", String)
            ...    ]
            ...

        Once registered, a model will become accessible as an attribute of the
        :data:`~cosmic.api.API.models` object.
        """

        model_cls.name = name = model_cls.__name__
        model_cls.api = self

        self._validate_model(model_cls)

        self._models[name] = model_cls

        methods = {}
        self.model_funcs[name] = {}
        for method in MODEL_METHODS:
            methods[method] = method in model_cls.methods
            self.model_funcs[name][method] = getattr(model_cls, method)
        self.model_funcs[name]['validate_patch'] = \
            getattr(model_cls, 'validate_patch')

        self.api_spec['models'][unicode(name)] = {
            "properties": OrderedDict(model_cls.properties),
            "links": OrderedDict(model_cls.links),
            "query_fields": OrderedDict(model_cls.query_fields),
            "list_metadata": OrderedDict(model_cls.list_metadata),
            "methods": methods,
        }
        setattr(self.models, name, model_cls)

        return model_cls

    def _validate_model(self, model_cls):

        link_names = set(dict(model_cls.links).keys())
        field_names = set(dict(model_cls.properties).keys())

        if link_names & field_names:
            raise SpecError(
                "Model cannot contain a field and link with the same name: {}".format(
                    model_cls.name))

        for name in link_names | field_names:
            validate_underscore_identifier(name)

        if 'id' in link_names | field_names:
            raise SpecError("'id' is a reserved name.")
