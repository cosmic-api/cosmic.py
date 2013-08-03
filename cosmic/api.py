from __future__ import unicode_literals

import json
import inspect
import requests
from multiprocessing import Process
from collections import OrderedDict

from teleport import *

from flask import Blueprint, Flask

from .actions import Function
from .models import Model, RemoteModel, prep_model
from .tools import GetterNamespace, get_args, assert_is_compatible, deserialize_json, validate_underscore_identifier
from .http import *
from . import cosmos




class API(BasicWrapper):
    type_name = "cosmic.API"

    schema = Struct([
        required("name", String),
        optional("homepage", String),
        required("models", OrderedMap(Struct([
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
            ]))),
            required("sets", OrderedMap(Struct([
                required(u"model", Schema),
                optional(u"doc", String)
            ]))),
        ]))),
        required("actions", OrderedMap(Function)),
    ])

    def __init__(self, name, homepage=None):
        self.name = name
        self.homepage = homepage
        self._models = OrderedDict()
        self._actions = OrderedDict()

        self.actions = GetterNamespace(self._get_function_callable)
        self.models = GetterNamespace(
            get_item=self._models.__getitem__,
            get_all=self._models.keys)

        # Add to registry so we can reference its models
        cosmos.apis[self.name] = self

    @staticmethod
    def assemble(datum):
        api = API(name=datum["name"], homepage=datum.get("homepage", None))
        api._actions = datum["actions"]

        for name, modeldef in datum["models"].items():
            M = cosmos.M("%s.%s" % (api.name, name))

            M.api = api
            M.properties = modeldef["data_schema"].param.items()
            M.query_fields = modeldef["query_fields"].items()
            M.links = modeldef["links"].items()
            M.sets = modeldef["sets"].items()
            prep_model(M)

            api._models[name] = M

        return api

    @staticmethod
    def disassemble(datum):
        models = OrderedDict()
        for model_cls in datum._models.values():
            models[unicode(model_cls.__name__)] = {
                "data_schema": Struct(model_cls.properties),
                "links": OrderedDict(model_cls.links),
                "query_fields": OrderedDict(model_cls.query_fields),
                "sets": OrderedDict(model_cls.sets)
            }
        return {
            "name": datum.name,
            "homepage": datum.homepage,
            "actions": datum._actions,
            "models": models
        }

    @staticmethod
    def load(url):
        """Given a spec URL, loads the JSON form of an API and deserializes
        it, returning the :class:`~cosmic.api.API` object.
        """
        res = requests.get(url)
        api = API.from_json(res.json)
        # Set the API url to be the spec URL, minus the /spec.json
        api.url = url[:-10]
        api._request = RequestsPlugin(api.url)
        return api

    def get_blueprint(self):
        """Return a :class:`flask.blueprints.Blueprint` instance containing
        everything necessary to run your API. You may use this to augment an
        existing Flask website with an API::

            from flask import Flask
            from cosmic import API

            hackernews = Flask(__name__)
            hnapi = API("hackernews")

            hackernews.register_blueprint(
                hnapi.get_blueprint(),
                url_prefix="/api")
        """

        spec_view = Function(returns=API)
        spec_view.func = lambda payload: self

        view_func = FlaskViewAction(spec_view, "/spec.json", self)
        view_func.method = "GET"

        blueprint = Blueprint('cosmic', __name__)
        blueprint.add_url_rule(view_func.url,
            view_func=view_func.view,
            methods=[view_func.method],
            endpoint="spec")
        
        for name, function in self._actions.items():
            url = "/actions/%s" % name
            endpoint = "function_%s" % name
            view_func = FlaskViewAction(function, url, self)
            blueprint.add_url_rule(url,
                view_func=view_func.view,
                methods=[view_func.method],
                endpoint=endpoint)

        for name, model_cls in self._models.items():
            model_cls._list_poster.add_to_blueprint(blueprint)
            model_cls._list_getter.add_to_blueprint(blueprint)
            model_cls._model_getter.add_to_blueprint(blueprint)
            model_cls._model_putter.add_to_blueprint(blueprint)
            model_cls._model_deleter.add_to_blueprint(blueprint)
            for set_getter in model_cls._set_getters.values():
                set_getter.add_to_blueprint(blueprint)
            for set_putter in model_cls._set_putters.values():
                set_putter.add_to_blueprint(blueprint)

        return blueprint

    def get_flask_app(self, debug=False, url_prefix=None):
        """Returns a Flask application with nothing but the API blueprint
        registered.

        The *debug* parameter will determine whether Cosmic will propagate
        exceptions, letting them reach the debugger or swallow them up,
        returning proper HTTP error responses.
        """
        blueprint = self.get_blueprint()

        app = Flask(__name__, static_folder=None)
        # When debug is True, PROPAGATE_EXCEPTIONS will be implicitly True
        app.debug = debug
        app.register_blueprint(blueprint, url_prefix=url_prefix)

        return app

    def get_json_spec(self):
        return API.to_json(self)


    def run(self, url_prefix=None, api_key=None, registry_url_override=None, **kwargs): # pragma: no cover
        """Runs the API as a Flask app. All keyword arguments except
        *url_prefix* channelled into :meth:`Flask.run`.
        """
        debug = kwargs.get('debug', False)
        app = self.get_flask_app(debug=debug, url_prefix=url_prefix)

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

        with cosmos:
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

        .. code:: python

            random = API("random")

            @random.action(returns=Integer)
            def generate():
                "Random enough"
                return 9
        """
        def wrapper(func):
            name = unicode(func.__name__)
            validate_underscore_identifier(name)
            required, optional = get_args(func)

            if accepts:
                assert_is_compatible(accepts, required, optional)

            doc = inspect.getdoc(func)
            function = Function(accepts, returns, doc)
            function.func = func

            self._actions[name] = function

            return func
        return wrapper

    def _get_function_callable(self, name):
        function = self._actions[name]
        if hasattr(function, "func"):
            return function.func
        else:
            return FlaskViewAction(function, '/actions/' + name, self)

    def model(self, model_cls):
        """A decorator for registering a model with an API. The name of the
        model class is used as the name of the resulting model.

        .. code:: python

            from teleport import String
            from cosmic.models import Model

            dictionary = API("dictionary")

            @dictionary.model
            class Word(Model):
                data_schema = String

        """
        model_cls.api = self
        model_cls.type_name = "%s.%s" % (self.name, model_cls.__name__,)
        # Add to namespace
        self._models[unicode(model_cls.__name__)] = model_cls
        prep_model(model_cls)
        return model_cls


