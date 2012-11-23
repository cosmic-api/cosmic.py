import sys
import json
import requests

from flask import Flask, Blueprint, Response, request, abort, make_response
from flask.exceptions import JSONBadRequest

from apio.exceptions import APIError, SpecError, InvalidCallError
from apio.tools import get_arg_spec, apply_to_action_func, serialize_action_arguments, JSONPayload

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
        if name.startswith('apio') and name not in ['apio.api', 'apio.exceptions']:
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

    def __init__(self, api):
        self._api = api
        self._actions = []
        self.__all__ = []
        for spec in api.spec['actions']:
            action = RemoteAction(api, spec)
            self._actions.append(action)
            self.__all__.append(spec['name'])

    def __getattr__(self, action_name):
        print action_name, self.__all__
        if action_name not in self.__all__:
            raise SpecError("Action %s is not defined" % action_name)
        for action in self._actions:
            if action.spec['name'] == action_name:
                return action.call

class Action(object):

    def __init__(self, func):
        self.name = func.__name__
        self.spec = {
            "name": self.name,
            "returns": {
                "type": "any"
            }
        }
        self.raw_func = func
        arg_spec = get_arg_spec(func)
        if arg_spec:
            self.spec["accepts"] = arg_spec

    def call(self, *args, **kwargs):
        # This seems redundant, but is necessary to make sure local
        # actions behave same as remote ones
        data = serialize_action_arguments(*args, **kwargs)
        return apply_to_action_func(self.raw_func, data)

    def get_view(self, debug=False):
        """Wraps a user-defined action function to return a Flask view function
        that handles errors and returns proper HTTP responses"""
        def action_view():
            if request.headers.get('Content-Type', None) != "application/json":
                return json.dumps({
                    "error": 'Content-Type must be "application/json"'
                }), 400
            # If function takes no arguments, request must be empty
            if 'accepts' not in self.spec and request.data != "":
                return json.dumps({
                    "error": "%s takes no arguments. Request content must be empty" % self.name 
                }), 400
            # If function takes arguments, request cannot be empty
            if 'accepts' in self.spec and request.data == "":
                return json.dumps({
                    "error": "%s takes arguments. Request content cannot be empty" % self.name
                }), 400
            try:
                if request.data == "":
                    data = apply_to_action_func(self.raw_func, None)
                else:
                    data = apply_to_action_func(self.raw_func, JSONPayload(request.json))
            except JSONBadRequest:
                return json.dumps({
                    "error": "Invalid JSON"
                }), 400
            # If the user threw an APIError
            except APIError as err:
                return json.dumps({
                    "error": err.args[0]
                }), err.http_code
            # Any other exception should be handled gracefully
            except Exception as e:
                if debug: raise e
                return json.dumps({
                    "error": "Internal Server Error"
                }), 500
            return json.dumps(data)
        return action_view

class API(BaseAPI):

    def __init__(self, name=None, url=None, homepage=None, **kwargs):
        self._actions = []
        self.name = name
        self.url = url
        self.homepage = homepage
        self.actions = ActionDispatcher(self)

    @property
    def spec(self):
        spec = {
            "actions": [action.spec for action in self._actions],
            "name": self.name,
            "url": self.url
        }
        if self.homepage: spec['homepage'] = self.homepage
        return spec

    def get_blueprint(self, debug=False):
        """Returns a Flask Blueprint object with all of the API's routes set up.
        Use this if you want to integrate your API into a Flask application.
        """
        blueprint = Blueprint(self.name, __name__)
        for action in self._actions:
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
        """Runs the API as a Flask app. All arguments channelled into Flask#run
        except for `register_api`, which is a boolean that defaults to True
        and determines whether you want your API pushed to APIO index.
        """

        debug = kwargs.get('debug', False)
        if kwargs.pop('register_api', True):
            ensure_bootstrapped()
            apio_index.actions.register_api(self.spec)
        if 'dry_run' in kwargs.keys(): return
        app = Flask(__name__, static_folder=None)
        # Flask will catch exceptions to return a nice HTTP response
        # in debug mode, we want things to FAIL!
        app.config['PROPAGATE_EXCEPTIONS'] = debug
        blueprint = self.get_blueprint(debug=debug)
        app.register_blueprint(blueprint)
        app.run(*args, **kwargs)

    def action(self, func):
        """Registers the given function as an API action. To be used as a 
        decorator.
        """
        action = Action(func)
        self._actions.append(action)
        self.actions._actions.append(action)
        self.actions.__all__.append(func.__name__)
        return func

    @staticmethod
    def load(name_or_url):
        """Given an API name, loads the API and returns an API object. If given
        a spec URL, loads the API from the spec.
        """
        if name_or_url.startswith('http'):
            res = requests.get(name_or_url)
            spec = res.json
        else:
            ensure_bootstrapped()
            spec = apio_index.actions.get_spec(name_or_url)
        api = RemoteAPI(spec)
        return api

class RemoteAction(object):

    def __init__(self, api, spec):
        self.api = api
        self.spec = spec

    def call(self, *args, **kwargs):
        json_data = serialize_action_arguments(*args, **kwargs)
        if json_data:
            data = json.dumps(json_data.json)
        else:
            if 'accepts' in self.spec:
                raise SpecError("%s takes arguments" % action_name)
            data = ""
        url = self.api.url + '/actions/' + self.spec['name']
        headers = { 'Content-Type': 'application/json' }
        res = requests.post(url, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            raise APIError(res.json['error'])
        return res.json

 
class RemoteAPI(BaseAPI):

    def __init__(self, spec):
        self.spec = spec
        self.actions = ActionDispatcher(self)

    @property
    def name(self):
        return self.spec['name']

    @property
    def url(self):
        return self.spec['url']

