from __future__ import unicode_literals

import sys
import json
import requests
from teleport import *

from flask import Blueprint, Flask

from .actions import Action
from .models import Model
from .tools import Namespace
from .http import FlaskView
from . import cosmos




class ModelSerializer(BasicWrapper):
    type_name = "cosmic.Model"

    schema = Struct([
        required("name", String),
        optional("schema", Schema)
    ])

    @staticmethod
    def inflate(datum):
        # Take a schema and name and turn them into a model class
        class M(Model):
            schema = datum["schema"]
        M.__name__ = str(datum["name"])
        return M

    @staticmethod
    def deflate(datum):
        return {
            "name": datum.__name__,
            "schema": datum.schema
        }



class API(BasicWrapper):
    type_name = "cosmic.API"

    schema = Struct([
        required("name", String),
        optional("homepage", String),
        required("actions", Array(Action)),
        required("models", Array(ModelSerializer))
    ])

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
    def inflate(datum):
        return API(**datum)

    @staticmethod
    def deflate(datum):
        return {
            "name": datum.name,
            "homepage": datum.homepage,
            "actions": datum.actions._list,
            "models": datum.models._list
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
        for action in self.actions:
            url = "/actions/%s" % action.name
            endpoint = "action_%s" % action.name
            view_func = FlaskView(action.json_to_json, debug)
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

    def run(self, url_prefix=None, **kwargs): # pragma: no cover
        """Runs the API as a Flask app. All keyword arguments except
        *url_prefix* channelled into :meth:`Flask.run`.
        """
        debug = kwargs.get('debug', False)
        app = self.get_flask_app(debug=debug, url_prefix=url_prefix)
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

        """
        model_cls.api = self
        model_cls.type_name = "%s.%s" % (self.name, model_cls.__name__,)
        # Add to namespace
        self.models.add(model_cls.__name__, model_cls)
        return model_cls


