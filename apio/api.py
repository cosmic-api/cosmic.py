from __future__ import unicode_literals

import sys
import json
import requests

# Still necessary for authentication
from flask import request

import apio.resources
from apio.exceptions import APIError, SpecError, ValidationError
from apio.actions import Action, RemoteAction, BaseAction
from apio.tools import Namespace, normalize
from apio.models import Model as BaseModel
from apio.models import serialize_json, ModelNormalizer, SchemaModel
from apio.http import ALL_METHODS, View, UrlRule, Response, CorsPreflightView, make_view
from apio.plugins import FlaskPlugin

API_SCHEMA = {
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
                "items": BaseAction.get_schema()
            }
        },
        {
            "name": "models",
            "required": True,
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": [
                        {
                            "name": "name",
                            "schema": {"type": "string"},
                            "required": True,
                        },
                        {
                            "name": "schema",
                            "schema": {"type": "core.Schema"},
                            "required": True,
                        }
                    ]
                }
            }
        }
    ]
}

# The apio-index API is saved here for convenience
apio_index = None

def clear_module_cache():
    global apio_index
    for name in sys.modules.keys():
        if name.startswith('apio.index'):
            del sys.modules[name]
    apio_index = None

def ensure_bootstrapped():
    """Ensures the APIO index API is loaded. Call this before trying
    API.load
    """
    global apio_index
    if not apio_index:
        data = json.dumps("apio-index")
        headers = { 'Content-Type': 'application/json' }
        res = requests.post("http://api.apio.io/actions/get_spec_by_name", data=data,
            headers=headers)
        apio_index = RemoteAPI(res.json)
        sys.modules.setdefault('apio.apio_index', apio_index)

class BaseAPI(object):
    def __init__(self):
        # Custom metaclass. When you inherit from Model, the new class
        # will be registered as part of the API
        self.actions = Namespace()
        self.models = models = Namespace()
        self.resources = resources = Namespace()
        class ModelHook(type):
            def __new__(meta, name, bases, attrs):
                cls = super(ModelHook, meta).__new__(meta, str(name), bases, attrs)
                if name != "Model":
                    # Raise ValidationError if model schema is invalid
                    normalize({"type": "core.Schema"}, cls.schema)
                    models.add(name, cls)
                return cls
        class Model(BaseModel):
            __metaclass__ = ModelHook
        self.Model = Model
        class ResourceHook(type):
            def __new__(meta, name, bases, attrs):
                cls = super(ResourceHook, meta).__new__(meta, str(name), bases, attrs)
                if name != "Resource":
                    # Make sure the class name ends with Resource
                    if not name.endswith("Resource"):
                        raise ValidationError("Resource class name must end with Resource")
                    # And then trim the name
                    name = name[:-len("Resource")]
                    cls.name = name
                    resources.add(name, cls)
                return cls
        class Resource(apio.resources.Resource):
            __metaclass__ = ResourceHook
        self.Resource = Resource

class API(BaseAPI):

    def __init__(self, name=None, url=None, homepage=None, **kwargs):
        super(API, self).__init__()
        self.name = name
        self.url = url
        self.homepage = homepage
        sys.modules['apio.index.' + name] = self

    @property
    def spec(self):
        models = []
        for model in self.models:
            models.append({
                'name': model.__name__,
                'schema': model.schema
            })
        spec = {
            "actions": [action.serialize() for action in self.actions],
            "models": models,
            "name": self.name,
            "url": self.url
        }
        if self.homepage: spec['homepage'] = self.homepage
        return serialize_json(spec)

    def get_rules(self, debug=False):
        """Get a list of URL rules necessary for implementing this API

        :param debug:
            Will be passed into the :class:`apio.http.View`
            constructor of all the views in the app
        :returns:
            A list of :class:`apio.http.UrlRule` objects
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
        string argument that, if set, triggers a call to APIO index to
        register the API.
        """
        debug = kwargs.get('debug', False)
        api_key = kwargs.pop('api_key', None)
        url_prefix = kwargs.pop('url_prefix', None)
        if api_key:
            ensure_bootstrapped()
            apio_index.actions.register_spec({
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
                accepts = SchemaModel(ModelNormalizer(SchemaModel)).normalize(accepts)
            except ValidationError:
                raise SpecError("'%s' was passed an invalid accepts schema" % self.name)
        if returns:
            try:
                returns = SchemaModel(ModelNormalizer(SchemaModel)).normalize(returns)
            except ValidationError:
                raise SpecError("'%s' was passed an invalid returns schema" % self.name)

        def wrapper(func):
            name = func.__name__
            action = Action(func, accepts=accepts, returns=returns)
            self.actions.add(name, action)
            return func
        return wrapper

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
            spec = apio_index.actions.get_spec_by_name(name).data
        api = RemoteAPI(spec)
        sys.modules["apio.index." + name] = api
        return api


class RemoteAPI(BaseAPI):

    def __init__(self, spec):
        super(RemoteAPI, self).__init__()
        self.spec = spec

        for spec in self.spec['actions']:
            action = RemoteAction.normalize(spec)
            action.api_url = self.url
            self.actions.add(spec['name'], action)

        for spec in self.spec['models']:
            name = spec['name']
            attrs = {
                "schema": spec['schema']
            }
            cls = self.Model.__metaclass__(name, (self.Model,), attrs)

    @property
    def name(self):
        return self.spec['name']

    @property
    def url(self):
        return self.spec['url']

