from __future__ import unicode_literals

import json
from functools import wraps
import inspect
import requests
from multiprocessing import Process
from collections import OrderedDict


from flask import Blueprint, Flask, request

from .actions import Action
from .models import BaseModel, prep_model, Cosmos
from .tools import GetterNamespace, get_args, assert_is_compatible, deserialize_json, validate_underscore_identifier
from .types import *
from .http import *
from . import cosmos


MODEL_METHODS = ['get_by_id', 'get_list', 'create', 'update', 'delete']


class Object(object):
    pass


class API(BasicWrapper):
    """An instance of this class represents a Cosmic API, whether it's your
    own API being served or a third-party API being consumed. In the former
    case, the API object is instantiated by the constructor and is bound to a
    database ORM and other user-defined functions. In the latter case, it is
    instantiated by the :meth:`API.load` method and these functions are
    replaced by automatically generated HTTP calls.

    One of the primary goals of Cosmic is to make local and remote APIs behave
    as similarly as possible.

    :param name: The API name is required, and should be unique
    :param homepage: If you like, the API spec may include a link to your homepage
    """
    type_name = "cosmic.API"

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

    def __init__(self, name, homepage=None):
        from .http import ClientHook

        self.name = name
        self.homepage = homepage
        self.server_hook = ServerHook()

        self._actions = OrderedDict()
        self.actions = Object()

        self._models = OrderedDict()
        self.models = Object()

        cosmos.apis[self.name] = self

    @staticmethod
    def assemble(datum):
        api = API(name=datum["name"], homepage=datum.get("homepage", None))

        for name, action in datum["actions"].items():
            action = Action(**action)
            api._actions[name] = action
            setattr(api.actions, name, action)
            action.api = api
            action.endpoint = ActionEndpoint(action, name)

        for name, modeldef in datum["models"].items():

            class M(BaseModel):
                type_name = "{}.{}".format(api.name, name)
                methods = []

                @classmethod
                def create(cls, **rep):
                    return cls._list_poster(**rep)

                @classmethod
                def update(cls, id, **rep):
                    return cls._model_putter(id, **rep)

                def delete(self):
                    return self.__class__._model_deleter(self)

                @classmethod
                def get_list(cls, **query):
                    return cls._list_getter(**query)

                @classmethod
                def get_by_id(cls, id):
                    return cls._model_getter(id)

            for method in MODEL_METHODS:
                if modeldef["methods"][method]:
                    M.methods.append(method)

            M.__name__ = str(name)

            M.api = api
            M.properties = modeldef["properties"].items()
            M.query_fields = modeldef["query_fields"].items()
            M.list_metadata = modeldef["list_metadata"].items()
            M.links = modeldef["links"].items()
            prep_model(M)

            api._models[name] = M
            setattr(api.models, name, M)

        return api

    @staticmethod
    def disassemble(datum):
        models = OrderedDict()
        actions = OrderedDict()
        for name, action in datum._actions.items():
            actions[name] = {
                "accepts": action.accepts,
                "returns": action.returns,
                "doc": action.doc
            }

        for model_cls in datum._models.values():
            models[unicode(model_cls.__name__)] = {
                "properties": OrderedDict(model_cls.properties),
                "links": OrderedDict(model_cls.links),
                "query_fields": OrderedDict(model_cls.query_fields),
                "list_metadata": OrderedDict(model_cls.list_metadata),
                "methods": {
                    "get_by_id": "get_by_id" in model_cls.methods,
                    "get_list": "get_list" in model_cls.methods,
                    "create": "create" in model_cls.methods,
                    "update": "update" in model_cls.methods,
                    "delete": "delete" in model_cls.methods,
                }
            }
        return {
            "name": datum.name,
            "homepage": datum.homepage,
            "actions": actions,
            "models": models
        }

    @staticmethod
    def load(url, verify=True):
        """Given a URL to a Cosmic API, fetch the API spec and build an API
        client:

        .. code:: python

            >>> planetarium = API.load("http://localhost:5000/spec.json") # doctest: +SKIP
            >>> planetarium.models.Sphere.get_by_id("0") # doctest: +SKIP
            <cosmic.models.Sphere object at 0x8f9ebcc>

        :param url: The API spec url, including ``/spec.json``
        :rtype: :class:`API` instance
        """
        res = requests.get(url, verify=verify)
        api = API.from_json(res.json())
        # Set the API url to be the spec URL, minus the /spec.json
        api.client_hook = ClientHook(url[:-10])
        return api


    def get_flask_app(self):
        """Returns a Flask application for the API."""

        app = Flask(__name__, static_folder=None)

        view_func = SpecEndpoint("/spec.json", self)
        app.add_url_rule(view_func.url,
            view_func=view_func.view,
            methods=[view_func.method],
            endpoint="spec")

        view_func = EnvelopeEndpoint(self)
        app.add_url_rule(view_func.url,
            view_func=view_func.view,
            methods=[view_func.method],
            endpoint="envelope")

        for name, action in self._actions.items():
            endpoint = "function_%s" % name
            view_func = action.endpoint
            app.add_url_rule(view_func.url,
                view_func=view_func.view,
                methods=[view_func.method],
                endpoint=endpoint)

        for name, model_cls in self._models.items():
            handlers = {
                'create': model_cls._list_poster,
                'get_list': model_cls._list_getter,
                'get_by_id': model_cls._model_getter,
                'update': model_cls._model_putter,
                'delete': model_cls._model_deleter
            }
            for method, handler in handlers.items():
                if method in model_cls.methods:
                    args = handler.get_url_rule()
                    args['view_func'] = args['view_func']
                    app.add_url_rule(**args)

        return app

    def run(self, api_key=None, registry_url_override=None, **kwargs): # pragma: no cover
        """Runs the API as a Flask app. All keyword arguments are channelled
        into :meth:`Flask.run`.
        """
        debug = kwargs.get('debug', False)
        app = self.get_flask_app()
        app.debug = debug

        if api_key:
            self.submit_spec(api_key, registry_url_override=None)
        app.run(**kwargs)

    def submit_spec(self, api_key, registry_url_override=None): # pragma: no cover

        def register_spec(url, api_key, spec):
            import requests
            headers = {'Content-Type': 'application/json'}
            data = json.dumps({
                "api_key": api_key,
                "spec": spec
            })
            requests.post(url, data=data, headers=headers)

        spec = API.to_json(self)

        url = "https://registry.cosmic-api.com/actions/register_spec"
        if registry_url_override:
            url = registry_url_override
        p = Process(target=register_spec, args=(url, api_key, spec,))
        p.start()
        return p

    def action(self, accepts=None, returns=None):
        """A decorator for creating actions out of functions and registering
        them with the API.

        The *accepts* parameter is a schema that describes the input of the
        function, *returns* is a schema that describes the output of the
        function. The name of the function becomes the name of the action.

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
            action = Action(accepts, returns, doc)
            action.api = self
            action.func = func
            action.endpoint = ActionEndpoint(action, name)

            self._actions[name] = action
            setattr(self.actions, name, action)

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

        .. code:: python

            >>> w = dictionary.models.Word.from_json({"text": "dog"})
            >>> w.text
            u'dog'

        """
        model_cls.api = self
        model_cls.type_name = "%s.%s" % (self.name, model_cls.__name__,)
        prep_model(model_cls)

        self._models[model_cls.__name__] = model_cls
        setattr(self.models, model_cls.__name__, model_cls)

        return model_cls


