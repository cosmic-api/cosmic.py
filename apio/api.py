import sys
import json
import requests

from flask import Flask, Blueprint, Response, request, make_response
from flask.exceptions import JSONBadRequest

import apio.resources
from apio.exceptions import APIError, SpecError, InvalidCallError, ValidationError
from apio.actions import Action, RemoteAction
from apio.tools import Namespace, normalize

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
                "items": {
                    "type": "object",
                    "properties": [
                        {
                            "name": "name",
                            "schema": {"type": "string"},
                            "required": True
                        },
                        {
                            "name": "accepts",
                            "schema": {"type": "schema"},
                            "required": False
                        },
                        {
                            "name": "returns",
                            "schema": {"type": "schema"},
                            "required": True
                        }
                    ]
                }
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
                            "schema": {"type": "schema"},
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
        res = requests.post("http://api.apio.io/actions/get_spec", data=data,
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
                cls = super(ModelHook, meta).__new__(meta, name, bases, attrs)
                if name != "Model":
                    # Raise ValidationError if model schema is invalid
                    normalize({"type": "schema"}, cls.schema)
                    models.add(name, cls)
                return cls
        class Model(object):
            __metaclass__ = ModelHook
            schema = {"type": "any"}
            def __init__(self, json_data):
                self.data = normalize(self.schema, json_data)
                self.validate()
            def validate(self):
                pass
        self.Model = Model
        class ResourceHook(type):
            def __new__(meta, name, bases, attrs):
                cls = super(ResourceHook, meta).__new__(meta, name, bases, attrs)
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
            "actions": [action.spec for action in self.actions],
            "models": models,
            "name": self.name,
            "url": self.url
        }
        if self.homepage: spec['homepage'] = self.homepage
        return spec

    def get_blueprint(self, debug=False):
        """Returns a Flask Blueprint object with all of the API's
        routes set up. Use this if you want to integrate your API into
        a Flask application.
        """
        blueprint = Blueprint(self.name, __name__)
        for action in self.actions:
            action.add_to_blueprint(blueprint, debug=debug)
        for resource in self.resources:
            resource().add_to_blueprint(blueprint, debug=debug)
        @blueprint.route('/spec.json')
        def getspec():
            spec = json.dumps(self.spec)
            return Response(spec, mimetype="application/json")
        return blueprint

    def get_test_app(self):
        """Returns a Flask test client
        """
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.get_blueprint(), url_prefix="/api")
        return app

    def run(self, *args, **kwargs):
        """Runs the API as a Flask app. All arguments channelled into
        Flask#run except for `register_api`, which is a boolean that
        defaults to True and determines whether you want your API
        pushed to APIO index.
        """
        debug = kwargs.get('debug', False)
        if kwargs.pop('register_api', True):
            ensure_bootstrapped()
            apio_index.actions.register_api(self.spec)
        if 'dry_run' not in kwargs.keys(): # pragma: no cover
            app = Flask(__name__, static_folder=None)
            # Flask will catch exceptions to return a nice HTTP
            # response in debug mode, we want things to FAIL!
            app.config['PROPAGATE_EXCEPTIONS'] = debug
            blueprint = self.get_blueprint(debug=debug)
            app.register_blueprint(blueprint)
            app.run(*args, **kwargs)

    def action(self, accepts=None, returns=None):
        """Registers the given function as an API action. To be used
        as a decorator.
        """
        def wrapper(func):
            name = func.__name__
            self.actions.add(name, Action(func, accepts=accepts, returns=returns))
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
            spec = apio_index.actions.get_spec(name)
        api = RemoteAPI(spec)
        sys.modules["apio.index." + name] = api
        return api


class RemoteAPI(BaseAPI):

    def __init__(self, spec):
        super(RemoteAPI, self).__init__()
        self.spec = spec

        for spec in self.spec['actions']:
            self.actions.add(spec['name'], RemoteAction(spec, self.url))

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

