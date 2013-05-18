from __future__ import unicode_literals

import sys
import json
import requests
import teleport
from werkzeug.routing import Map, Rule

from .actions import Action, ActionSerializer
from .models import Model
from .tools import Namespace
from .http import FlaskPlugin
from . import cosmos




class ModelSerializer(object):
    match_type = "cosmic.Model"

    schema = teleport.Struct([
        teleport.required("name", teleport.String()),
        teleport.optional("schema", teleport.Schema())
    ])

    def deserialize(self, datum):
        opts = self.schema.deserialize(datum)
        # Take a schema and name and turn them into a model class
        class M(Model):
            schema = opts["schema"]
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
            model.api = self
            self.models.add(model.__name__, model)
        # Add to registry so we can reference its models
        cosmos.apis[self.name] = self

    @staticmethod
    def load(url):
        """Given a spec URL, loads the JSON form of an API and deserializes
        it, returning the :class:`~cosmic.api.API` object.
        """
        res = requests.get(url)
        api = APISerializer().deserialize(res.json)
        # Set the API url to be the spec URL, minus the /spec.json
        api.url = url[:-10]
        # Once the API has been added to the cosmos, force lazy models to
        # evaluate.
        cosmos.force()
        return api

    def get_map(self, debug=False):
        def spec_view(payload):
            return teleport.Box(APISerializer().serialize(self))
        m = Map([
            Rule("/spec.json", methods=["GET"], endpoint=spec_view)
        ])
        for action in self.actions:
            url = "/actions/%s" % action.name
            m.add(Rule(url, methods=["POST"], endpoint=action.json_to_json))

        return m

    def get_flask_app(self, debug=False, url_prefix=""):
        """Returns a Flask application.
        """
        plugin = FlaskPlugin(
            setup_func=self.context_func,
            url_prefix=url_prefix,
            debug=debug,
            werkzeug_map=self.get_map(debug=debug))

        plugin.app.wsgi_app = cosmos.middleware(plugin.app.wsgi_app)
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

        The *accepts* parameter is a schema that will deserialize the input of
        the action, *returns* is a schema that will serialize the output of
        the action. The name of the function becomes the name of the action.
        Internally :meth:`~cosmic.actions.Action.from_func` is used.

        .. code:: python

            from teleport import Integer

            random = API("random")

            @random.action(returns=Integer())
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

            from teleport import String

            dictionary = API("dictionary")

            @dictionary.model
            class Word(object):
                schema = String()

                def __init__(self, text):
                    self.text = text

                def serialize_self(self):
                    return self.text

                @classmethod
                def deserialize_self(cls, datum):
                    datum = cls.schema.deserialize(datum)
                    return cls(datum)
        """
        model_cls.api = self
        # Add to namespace
        self.models.add(model_cls.__name__, model_cls)
        return model_cls

    def context_func(self, headers):
        return {}

    def context(self, func):
        """Registers the given function as an authentication function for the
        API.
        """
        self.context_func = func
        return func


class APISerializer(object):
    match_type = "cosmic.API"

    schema = teleport.Struct([
        teleport.required("name", teleport.String()),
        teleport.optional("homepage", teleport.String()),
        teleport.required("actions", teleport.Array(ActionSerializer())),
        teleport.required("models", teleport.Array(ModelSerializer()))
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

