from __future__ import unicode_literals

import json
import requests
from multiprocessing import Process
from collections import OrderedDict

from teleport import *

from flask import Blueprint, Flask

from .actions import Function
from .models import Model
from .tools import GetterNamespace, get_args, assert_is_compatible
from .http import FlaskView, Callable
from . import cosmos




class ModelSerializer(BasicWrapper):
    type_name = "cosmic.Model"

    schema = Struct([
        required("name", String),
        optional("schema", Schema)
    ])

    @staticmethod
    def assemble(datum):
        # Take a schema and name and turn them into a model class
        class M(Model):
            schema = datum["schema"]
        M.__name__ = str(datum["name"])
        return M

    @staticmethod
    def disassemble(datum):
        return {
            "name": datum.__name__,
            "schema": datum.schema
        }



class API(BasicWrapper):
    type_name = "cosmic.API"

    schema = Struct([
        required("name", String),
        optional("homepage", String),
        required("models", Array(ModelSerializer)),
        required("actions", OrderedMap(Function))
    ])

    def __init__(self, name, homepage=None, models=[], actions=None):
        self.name = name
        self.homepage = homepage

        if actions:
            self._actions = actions
        else:
            self._actions = OrderedDict()

        self._models = OrderedDict()
        # Populate it if we have initial data
        for model in models:
            model.api = self
            self._models[model.__name__] = model

        self.actions = GetterNamespace(self._get_function_callable)
        self.models = GetterNamespace(
            get_item=self._models.__getitem__,
            get_all=self._models.keys)

        # Add to registry so we can reference its models
        cosmos.apis[self.name] = self

    @staticmethod
    def assemble(datum):
        return API(**datum)

    @staticmethod
    def disassemble(datum):
        return {
            "name": datum.name,
            "homepage": datum.homepage,
            "actions": datum._actions,
            "models": datum._models.values()
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
        # Once the API has been added to the cosmos, force lazy models to
        # evaluate.
        cosmos.force()
        return api

    def get_blueprint(self, debug=False):
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
        
        The *debug* parameter will determine whether Cosmic will propagate
        exceptions, letting them reach the debugger or swallow them up,
        returning proper HTTP error responses.
        """

        def spec_view(payload):
            return Box(self.get_json_spec())

        blueprint = Blueprint('cosmic', __name__)
        blueprint.add_url_rule("/spec.json",
            view_func=FlaskView(spec_view, debug),
            methods=["GET"],
            endpoint="spec")
        for name, function in self._actions.items():
            url = "/actions/%s" % name
            endpoint = "function_%s" % name
            view_func = FlaskView(function.json_to_json, debug)
            blueprint.add_url_rule(url,
                view_func=view_func,
                methods=["POST"],
                endpoint=endpoint)
        return blueprint

    def get_flask_app(self, debug=False, url_prefix=None):
        """Returns a Flask application with nothing but the API blueprint
        registered.
        """
        blueprint = self.get_blueprint(debug=debug)

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
            def register_spec(self, url, api_key, spec):
                import requests
                headers = {'Content-Type': 'application/json'}
                data = {
                    "api_key": api_key,
                    "spec": spec
                }
                requests.post(url, data=data, headers=headers)

            with cosmos:
                spec = API.to_json(self)
            url = "https://registry.cosmic-api.com/actions/register_spec"
            if registry_url_override:
                url = registry_url_override
            p = Process(target=self.register_spec, args=(url, api_key, spec,))
            p.start()
        app.run(**kwargs)


    def action(self, accepts=None, returns=None, doc=None):
        """A decorator for creating actions out of functions and registering
        them with the API.

        The *accepts* parameter is a schema that describes the input of the
        function, *returns* is a schema that describes the output of the
        function. The name of the function becomes the name of the action.

        .. code:: python

            random = API("random")

            @random.action(returns=Integer)
            def generate():
                return 9
        """
        def wrapper(func):
            name = unicode(func.__name__)
            required, optional = get_args(func)

            if accepts:
                assert_is_compatible(accepts, required, optional)

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
            url = self.url + '/actions/' + name
            return Callable(function, url)

    def model(self, model_cls):
        """A decorator for registering a model with an API. The name of the
        model class is used as the name of the resulting model.

        .. code:: python

            from teleport import String
            from cosmic.models import Model

            dictionary = API("dictionary")

            @dictionary.model
            class Word(Model):
                schema = String

        """
        model_cls.api = self
        model_cls.type_name = "%s.%s" % (self.name, model_cls.__name__,)
        # Add to namespace
        self._models[model_cls.__name__] = model_cls
        return model_cls


