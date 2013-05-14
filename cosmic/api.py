from __future__ import unicode_literals

import sys
import json
import requests

# Still necessary for authentication
from flask import request

from .actions import Action, ActionSerializer
from .tools import Namespace, CosmicTypeMap
from .http import UrlRule, CorsPreflightView, make_view
from .plugins import FlaskPlugin

import teleport



class APIModelSerializer(object):
    match_type = "cosmic.APIModel"

    schema = teleport.Struct([
        teleport.required("name", teleport.String()),
        teleport.optional("schema", teleport.Schema())
    ])

    def deserialize(self, datum):
        opts = self.schema.deserialize(datum)
        # Take a schema and name and turn them into a model class
        class M(object):
            @classmethod
            def get_schema(cls):
                return opts["schema"]
        M.__name__ = str(opts["name"])
        return M

    def serialize(self, datum):
        return self.schema.serialize({
            "name": datum.__name__,
            "schema": datum.get_schema()
        })



class API(object):

    def __init__(self, name, homepage=None, actions=[], models=[]):
        self.name = name
        self.homepage = homepage
        # Create actions and models namespace
        self.actions = Namespace()
        self.models = Namespace()
        # Populate them if we have initial data
        for action in actions:
            action.api = self
            self.actions.add(action.name, action)
        for model in models:
            self.models.add(model.__name__, model)
        # Add to registry so we can reference its models
        sys.modules['cosmic.registry.' + self.name] = self

    @staticmethod
    def load(url):
        """Given a spec URL, loads it and normalizes, returning the
        :class:`~cosmic.api.API` object.
        """
        res = requests.get(url)
        spec = res.json
        name = spec['name']
        #api = API.normalize(res.json)
        api = APISerializer().deserialize(res.json)
        # Set the API url to be the spec URL, minus the /spec.json
        api.url = url[:-10]
        return api

    def get_rules(self, debug=False):
        """Get a list of URL rules necessary for implementing this API The
        *debug* parameter will be passed into the :class:`cosmic.http.View`
        constructor of all the views in the API. Returns a list of
        :class:`cosmic.http.UrlRule` objects.
        """
        rules = []
        for action in self.actions:
            view = action.get_view(debug=debug)
            cors = CorsPreflightView(["POST"])
            url = "/actions/%s" % action.name
            rules.append(UrlRule(url, action.name, view))
            rules.append(UrlRule(url, action.name + '_cors', cors))
        @make_view("GET")
        def spec_view(payload):
            return teleport.Box(APISerializer().serialize(self))
        rules.append(UrlRule("/spec.json", "spec", spec_view))
        return rules

    def get_flask_app(self, debug=False, url_prefix=None):
        """Returns a Flask application.
        """
        rules = self.get_rules(debug=debug)
        plugin = FlaskPlugin(rules,
            setup_func=self.context_func,
            url_prefix=url_prefix,
            debug=debug)

        plugin.app.wsgi_app = CosmicTypeMap.middleware(plugin.app.wsgi_app)
        return plugin.app

    def run(self, url_prefix=None, **kwargs): # pragma: no cover
        """Runs the API as a Flask app. All keyword arguments except
        *url_prefix* channelled into :meth:`Flask.run`.
        """
        debug = kwargs.get('debug', False)
        app = self.get_flask_app(debug=debug, url_prefix=url_prefix)
        # Flask will catch exceptions to return a nice HTTP
        # response in debug mode, we want things to FAIL!
        app.config['PROPAGATE_EXCEPTIONS'] = debug
        app.run(**kwargs)


    def action(self, accepts=None, returns=None):
        """A decorator for creating actions out of functions and registering
        them with the API.

        The *accepts* parameter is a :class:`~cosmic.models.Schema` instance
        that will normalize the input of the action, *returns* is a
        :class:`~cosmic.models.Schema` instance that will serialize the input
        of the action. The name of the function becomes the name of the
        action. Internally :meth:`~cosmic.actions.Action.from_func` is used.

        .. code:: python

            from cosmic.tools import normalize_schema

            random = API("random")

            @squeegee.action(returns=normalize_schema({"type": "integer"}))
            def generate():
                return 9
        """
        def wrapper(func):
            name = func.__name__
            action = Action.from_func(func, accepts=accepts, returns=returns)
            action.api = self
            self.actions.add(name, action)
            return func
        return wrapper

    def model(self, model_cls):
        """A decorator for registering a model with an API. The name of the
        model class is used as the name of the resulting model.

        .. code:: python

            from cosmic.tools import normalize_schema
            from cosmic.models import Model

            dictionary = API("dictionary")

            @dictionary.model
            class Word(Model):
                schema = normalize_schema({"type": "string"})
        """
        # Add to namespace
        self.models.add(model_cls.__name__, model_cls)
        return model_cls

    def context_func(self, headers):
        return {}

    def context(self, func):
        """Registers the given function as an authentication function
        for the API.
        """
        self.context_func = func
        return func


class APISerializer(object):
    match_type = "cosmic.API"

    schema = teleport.Struct([
        teleport.required("name", teleport.String()),
        teleport.optional("homepage", teleport.String()),
        teleport.required("actions", teleport.Array(ActionSerializer())),
        teleport.required("models", teleport.Array(APIModelSerializer()))
    ])

    def deserialize(self, datum):
        opts = self.schema.deserialize(datum)
        return API(**opts)

    def serialize(self, datum):
        return self.schema.serialize({
            "name": datum.name,
            "homepage": datum.homepage,
            "actions": datum.actions._list,
            "models": datum.models._list
        })

