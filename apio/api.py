import sys
import json
import requests

from flask import Flask, Blueprint, Response, request
from flask.exceptions import JSONBadRequest

from apio.exceptions import APIError, SpecError, InvalidCallError
from apio.actions import Action, RemoteAction

API_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "required": True
        },
        "url": {
            "type": "string",
            "required": True
        },
        "homepage": {
            "type": "string"
        },
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": { "type": "string" },
                    "accepts": {
                        "$ref": "http://json-schema.org/draft-03/schema#"
                    },
                    "returns": {
                        "$ref": "http://json-schema.org/draft-03/schema#"
                    }
                }
            }
        }
    }
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
    """Ensures the APIO index API is loaded. Call this before trying API.load"""
    global apio_index
    if not apio_index:
        data = json.dumps("apio-index")
        headers = { 'Content-Type': 'application/json' }
        res = requests.post("http://api.apio.io/actions/get_spec", data=data,
            headers=headers)
        apio_index = RemoteAPI(res.json)
        sys.modules.setdefault('apio.apio_index', apio_index)


class BaseAPI(object):
    pass

class ActionDispatcher(object):
    """Essentially a sorted dictionary. Allows to reference actions as attributes
    and implements __all__ so that the instance can be treated as a module.
    """

    def __init__(self):
        self._list = []
        self._dict = {}
    
    def __iter__(self):
        """Allow iterating through actions"""
        return self._list.__iter__()
    
    @property
    def __all__(self):
        return [action.spec['name'] for action in self._list]

    @property
    def specs(self):
        return [action.spec for action in self._list]

    def add(self, action):
        self._list.append(action)
        self._dict[action.spec['name']] = action

    def __getattr__(self, action_name):
        try:
            return self._dict[action_name]
        except KeyError:
            raise SpecError("Action %s is not defined" % action_name)

class API(BaseAPI):

    def __init__(self, name=None, url=None, homepage=None, **kwargs):
        self.name = name
        self.url = url
        self.homepage = homepage
        self.actions = ActionDispatcher()

    @property
    def spec(self):
        spec = {
            "actions": self.actions.specs,
            "name": self.name,
            "url": self.url
        }
        if self.homepage: spec['homepage'] = self.homepage
        return spec

    def get_blueprint(self, debug=False):
        """Returns a Flask Blueprint object with all of the API's
        routes set up.  Use this if you want to integrate your API
        into a Flask application.
        """
        blueprint = Blueprint(self.name, __name__)
        for action in self.actions:
            name = action.spec['name']
            view = action.get_view(debug=debug)
            url = "/actions/%s" % name
            blueprint.add_url_rule(url, name, view, methods=['POST'])
        @blueprint.route('/spec.json')
        def getspec():
            spec = json.dumps(self.spec)
            return Response(spec, mimetype="application/json")
        return blueprint

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
            self.actions.add(Action(func, accepts=accepts, returns=returns))
            return func
        return wrapper

    def authentication(self, func):
        """Registers the given function as an authentication function
        for the API. The authentication function takes a dict of
        headers as its single argument and returns user-related data
        or raises AuthenticationError
        """
        def authenticate():
            return func(request.headers)
        self.authenticate = authenticate
        return func

    @staticmethod
    def load(name_or_url):
        """Given an API name, loads the API and returns an API
        object. If given a spec URL, loads the API from the spec.
        """
        if name_or_url.startswith('http'):
            res = requests.get(name_or_url)
            spec = res.json
        else:
            ensure_bootstrapped()
            spec = apio_index.actions.get_spec(name_or_url)
        api = RemoteAPI(spec)
        return api


class RemoteAPI(BaseAPI):

    def __init__(self, spec):
        self.spec = spec
        self.actions = ActionDispatcher()

        for spec in self.spec['actions']:
            self.actions.add(RemoteAction(spec, self.url))

    @property
    def name(self):
        return self.spec['name']

    @property
    def url(self):
        return self.spec['url']

