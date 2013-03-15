from __future__ import unicode_literals

import sys
import json
import requests

# Still necessary for authentication
from flask import request

import cosmic.resources
from cosmic.exceptions import APIError, SpecError, ValidationError
from cosmic.actions import Action
from cosmic.tools import Namespace, normalize, normalize_schema, fetch_model
from cosmic.models import Model as BaseModel
from cosmic.models import ClassModel, Schema, SimpleSchema
from cosmic.http import ALL_METHODS, View, UrlRule, Response, CorsPreflightView, make_view
from cosmic.plugins import FlaskPlugin

# The Cosmic Registry API is saved here for convenience
cosmic_registry = None

def clear_module_cache():
    global cosmic_registry
    for name in sys.modules.keys():
        if name.startswith('cosmic.registry'):
            del sys.modules[name]
    cosmic_registry = None

def ensure_bootstrapped():
    """Ensures the Cosmic Registry API is loaded. Call this before trying
    API.load
    """
    global cosmic_registry
    if not cosmic_registry:
        data = json.dumps("cosmic-registry")
        headers = { 'Content-Type': 'application/json' }
        res = requests.post("http://api.cosmic.io/actions/get_spec_by_name", data=data,
            headers=headers)
        cosmic_registry = API.normalize(res.json, fetcher=fetch_model)
        sys.modules.setdefault('cosmic.cosmic_registry', cosmic_registry)


class APIModel(ClassModel):

    properties = [
        {
            "name": "name",
            "required": True,
            "schema": normalize_schema({"type": "string"})
        },
        {
            "name": "schema",
            "required": True,
            "schema": normalize_schema({"type": "schema"})
        }
    ]

    @classmethod
    def from_model_cls(cls, model_cls):
        return cls({
            "name": model_cls.__name__,
            "schema": model_cls.get_schema()
        })

    @classmethod
    def normalize(cls, datum, **kwargs):
        # Run the schema normalization, that's what ClassModel does
        inst = super(APIModel, cls).normalize(datum)
        # Take a schema and name and turn them into a model class
        class M(BaseModel):
            @classmethod
            def get_schema(cls):
                return inst.schema
        M.__name__ = str(inst.name)
        inst.model = M
        return inst



class API(BaseModel):

    def __init__(self, *args, **kwargs):
        super(API, self).__init__(*args, **kwargs)
        # Create actions and models namespace
        self.actions = Namespace()
        self.models = models = Namespace()
        # Populate them if we have initial data
        for action in self.data['actions']:
            action.api_url = self.url
            self.actions.add(action.name, action)
        for model in self.data['models']:
            self.models.add(model.name, model.model)
        # Add to registry so we can reference its models
        sys.modules['cosmic.registry.' + self.name] = self

    @classmethod
    def create(cls, name=None, url=None, homepage=None, **kwargs):
        return cls({
            "name": name,
            "url": url,
            "homepage": homepage,
            "actions": [],
            "models": []
        })

    @staticmethod
    def load(name_or_url):
        """Given an API name, loads the API and returns an API
        object. If given a spec URL, loads the API from the url.
        """
        if name_or_url.startswith('http'):
            res = requests.get(name_or_url)
            spec = res.json
            name = spec['name']
            return API.normalize(res.json, fetcher=fetch_model)
        else:
            name = name_or_url
            ensure_bootstrapped()
            return cosmic_registry.actions.get_spec_by_name(name)

    @property
    def name(self):
        return self.data['name']

    @property
    def url(self):
        return self.data['url']

    schema = normalize_schema({
        "type": "object",
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
                    "items": {"type": "cosmic.Action"}
                }
            },
            {
                "name": "models",
                "required": True,
                "schema": {
                    "type": "array",
                    "items": {"type": "cosmic.APIModel"}
                }
            }
        ]
    })

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
        @make_view("GET", None, {"type": "json"})
        def spec_view(payload):
            return self.serialize()
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
        string argument that, if set, triggers a call to Cosmic
        registry to register the API.
        """
        debug = kwargs.get('debug', False)
        api_key = kwargs.pop('api_key', None)
        url_prefix = kwargs.pop('url_prefix', None)
        if api_key:
            ensure_bootstrapped()
            cosmic_registry.actions.register_spec(api_key=api_key, spec=self)
        if 'dry_run' not in kwargs.keys(): # pragma: no cover
            app = self.get_flask_app(debug=debug, url_prefix=url_prefix)
            # Flask will catch exceptions to return a nice HTTP
            # response in debug mode, we want things to FAIL!
            app.config['PROPAGATE_EXCEPTIONS'] = debug
            app.run(*args, **kwargs)






    def action(self, accepts=None, returns={u"type": u"json"}):
        """Registers the given function as an API action. To be used
        as a decorator.
        """
        if accepts:
            try:
                accepts = normalize_schema(accepts)
            except ValidationError:
                raise SpecError("'%s' was passed an invalid accepts schema" % self.name)
        if returns:
            try:
                returns = normalize_schema(returns)
            except ValidationError:
                raise SpecError("'%s' was passed an invalid returns schema" % self.name)

        def wrapper(func):
            name = func.__name__
            action = Action.from_func(func, accepts=accepts, returns=returns)
            self.actions.add(name, action)
            self.data['actions'].append(action)
            return func
        return wrapper

    def model(self, model_cls):
        # Add to data
        self.data['models'].append(APIModel.from_model_cls(model_cls))
        # Add to namespace
        self.models.add(model_cls.__name__, model_cls)
        return model_cls

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
