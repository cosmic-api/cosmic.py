from __future__ import unicode_literals

import sys
import json
import requests

# Still necessary for authentication
from flask import request

import cosmic.resources
from cosmic.exceptions import APIError, SpecError, ValidationError
from cosmic.actions import Action, RemoteAction, BaseAction
from cosmic.tools import Namespace, normalize
from cosmic.models import Model as BaseModel
from cosmic.models import serialize_json, Schema, ObjectModel
from cosmic.http import ALL_METHODS, View, UrlRule, Response, CorsPreflightView, make_view
from cosmic.plugins import FlaskPlugin

# The cosmic-index API is saved here for convenience
cosmic_index = None

def clear_module_cache():
    global cosmic_index
    for name in sys.modules.keys():
        if name.startswith('cosmic.index'):
            del sys.modules[name]
    cosmic_index = None

def ensure_bootstrapped():
    """Ensures the COSMIC index API is loaded. Call this before trying
    API.load
    """
    global cosmic_index
    if not cosmic_index:
        data = json.dumps("cosmic-index")
        headers = { 'Content-Type': 'application/json' }
        res = requests.post("http://api.cosmic.io/actions/get_spec_by_name", data=data,
            headers=headers)
        cosmic_index = RemoteAPI(res.json)
        sys.modules.setdefault('cosmic.cosmic_index', cosmic_index)


class APIModel(BaseModel):

    schema = {
        "type": "object",
        "properties": [
            {
                "name": "name",
                "required": True,
                "schema": {"type": "string"}
            },
            {
                "name": "schema",
                "required": True,
                "schema": {"type": "core.Schema"}
            }
        ]
    }

    def serialize(self):
        return {
            u"name": self.data.__name__,
            u"schema": self.data.get_schema().serialize()
        }

    @classmethod
    def validate(cls, datum):
        # Take a schema and name and turn them into a model class
        class M(BaseModel):
            @classmethod
            def get_schema(cls):
                return datum['schema']
        M.__name__ = str(datum['name'])
        return M


API_SCHEMA = {"type": "object",
    "properties": [
        {
            "name": "name",
            "schema": {"type": "string"},
            "required": True
        },
        {
            "name": "url",
            "schema": {"type": "string"},
            "required": True
        },
        {
            "name": "homepage",
            "schema": {"type": "string"},
            "required": False
        },
        {
            "name": "actions",
            "required": True,
            "schema": {
                "type": "array",
                "items": BaseAction.get_schema().serialize()
            }
        },
        {
            "name": "models",
            "required": True,
            "schema": {
                "type": "array",
                "items": APIModel.get_schema().serialize()
            }
        }
    ]
}


class BaseAPI(object):
    def __init__(self):
        # Custom metaclass. When you inherit from Model, the new class
        # will be registered as part of the API
        self.actions = Namespace()
        self.models = models = Namespace()
        self.api_models = []


class API(BaseAPI):

    def __init__(self, name=None, url=None, homepage=None, **kwargs):
        super(API, self).__init__()
        self.name = name
        self.url = url
        self.homepage = homepage
        sys.modules['cosmic.index.' + name] = self

    @property
    def spec(self):
        spec = {
            "actions": [action.serialize() for action in self.actions],
            "models": [model.serialize() for model in self.api_models],
            "name": self.name,
            "url": self.url
        }
        if self.homepage: spec['homepage'] = self.homepage
        return serialize_json(spec)

    def get_rules(self, debug=False):
        """Get a list of URL rules necessary for implementing this API

        :param debug:
            Will be passed into the :class:`cosmic.http.View`
            constructor of all the views in the app
        :returns:
            A list of :class:`cosmic.http.UrlRule` objects
        """
        rules = []
        for action in self.actions:
            view = action.get_view(debug=debug)
            cors = CorsPreflightView(["POST"])
            url = "/actions/%s" % action.name
            rules.append(UrlRule(url, action.name, view))
            rules.append(UrlRule(url, action.name + '_cors', cors))
        @make_view("GET", None, {"type": "core.JSON"})
        def spec_view(payload):
            return self.spec
        rules.append(UrlRule("/spec.json", "spec", spec_view))
        return rules

    def get_flask_app(self, debug=False, url_prefix=None):
        """Returns a Flask test client
        """
        plugin = FlaskPlugin(self.get_rules(debug=debug), url_prefix=url_prefix, debug=debug)
        return plugin.app

    def run(self, *args, **kwargs):
        """Runs the API as a Flask app. All arguments channelled into
        :meth:`Flask.run` except for *api_key*, which is an optional
        string argument that, if set, triggers a call to COSMIC index to
        register the API.
        """
        debug = kwargs.get('debug', False)
        api_key = kwargs.pop('api_key', None)
        url_prefix = kwargs.pop('url_prefix', None)
        if api_key:
            ensure_bootstrapped()
            cosmic_index.actions.register_spec({
                "api_key": api_key,
                "spec": self.spec
            })
        if 'dry_run' not in kwargs.keys(): # pragma: no cover
            app = self.get_flask_app(debug=debug, url_prefix=url_prefix)
            # Flask will catch exceptions to return a nice HTTP
            # response in debug mode, we want things to FAIL!
            app.config['PROPAGATE_EXCEPTIONS'] = debug
            app.run(*args, **kwargs)

    def action(self, accepts=None, returns={u"type": u"core.JSON"}):
        """Registers the given function as an API action. To be used
        as a decorator.
        """
        if accepts:
            try:
                accepts = Schema.make_normalizer().normalize(accepts)
            except ValidationError:
                raise SpecError("'%s' was passed an invalid accepts schema" % self.name)
        if returns:
            try:
                returns = Schema.make_normalizer().normalize(returns)
            except ValidationError:
                raise SpecError("'%s' was passed an invalid returns schema" % self.name)

        def wrapper(func):
            name = func.__name__
            action = Action(func, accepts=accepts, returns=returns)
            self.actions.add(name, action)
            return func
        return wrapper

    def model(self, model_cls):
        # Raise ValidationError if model schema is invalid
        normalize({"type": "core.Schema"}, model_cls.schema)
        self.models.add(model_cls.__name__, model_cls)
        self.api_models.append(APIModel(model_cls))

    def authenticate(self):
        """Authenticates the user based on request headers. Returns
        user-related data upon successful authentication, raises
        AuthenticationError upon unsuccessful authentication and
        returns None if no authentication info was passed in.
        """
        return None

    def authentication(self, func):
        """Registers the given function as an authentication function
        for the API.
        """
        def authenticate():
            return func(request.headers)
        self.authenticate = authenticate
        return func

    @staticmethod
    def load(name_or_url):
        """Given an API name, loads the API and returns an API
        object. If given a spec URL, loads the API from the url.
        """
        if name_or_url.startswith('http'):
            res = requests.get(name_or_url)
            spec = res.json
            name = spec['name']
        else:
            name = name_or_url
            ensure_bootstrapped()
            spec = cosmic_index.actions.get_spec_by_name(name).data
        api = RemoteAPI(spec)
        sys.modules["cosmic.index." + name] = api
        return api


class RemoteAPI(BaseAPI):

    def __init__(self, spec):
        super(RemoteAPI, self).__init__()
        self.spec = spec

        for spec in self.spec['actions']:
            action = RemoteAction.from_json(spec)
            action.api_url = self.url
            self.actions.add(spec['name'], action)

        for spec in self.spec['models']:
            api_model = APIModel.from_json(spec)
            self.models.add(api_model.data.__name__, api_model.data)

    @property
    def name(self):
        return self.spec['name']

    @property
    def url(self):
        return self.spec['url']

