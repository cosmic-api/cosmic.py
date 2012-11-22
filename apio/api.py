import sys
import json
import requests

from flask import Flask, Blueprint, Response, request, abort, make_response
from flask.exceptions import JSONBadRequest

from apio.exceptions import *
from apio.tools import get_arg_spec

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

# Clears 
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
    def call(self, action_name, obj=None):
        return self.actions.__getattr__(action_name)(obj)


class API(BaseAPI):

    def __init__(self, name=None, url=None, homepage=None, **kwargs):
        self.actions = API.ActionDispatcher()
        self.name = name
        self.url = url
        self.homepage = homepage

    @property
    def spec(self):
        spec = {
            "actions": self.actions._specs,
            "name": self.name,
            "url": self.url
        }
        if self.homepage: spec['homepage'] = self.homepage
        return spec

    class ActionDispatcher(object):

        def __init__(self):
            self.__funcs = {}
            self._specs = []

        def _register_action_func(self, func):
            action_spec = {
                "name": func.__name__,
                "returns": {
                    "type": "any"
                }
            }
            self.__funcs[func.__name__] = func
            arg_spec = get_arg_spec(func)
            if arg_spec:
                action_spec["accepts"] = arg_spec
            self._specs.append(action_spec)
            return action_spec

        def _assert_action_defined(self, action_name):
            if action_name not in self.__funcs.keys():
                raise SpecError("Action %s is not defined" % action_name)

        def __getattr__(self, action_name):
            def func(obj=None):
                self._assert_action_defined(action_name)
                action_spec = None
                for spec in self._specs:
                    if spec['name'] == action_name:
                        action_spec = spec
                func = self.__funcs[action_name]
                if "accepts" not in action_spec:
                    return func()
                return func(obj)
            return func

    def _get_action_view(self, action_name, debug=False):
        """Wraps a user-defined action function to return a Flask view function
        that handles errors and returns proper HTTP responses"""
        def action_view():
            if request.headers.get('Content-Type', None) != "application/json":
                return json.dumps({
                    "error": 'Content-Type must be "application/json"'
                }), 400
            if request.data == "":
                return json.dumps(self.actions.__getattr__(action_name)())
            try:
                data = self.actions.__getattr__(action_name)(request.json)
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

    def get_blueprint(self, debug=False):
        """Returns a Flask Blueprint object with all of the API's routes set up.
        Use this if you want to integrate your API into a Flask application.
        """
        blueprint = Blueprint(self.name, __name__)
        for action_spec in self.actions._specs:
            name = action_spec['name']
            view = self._get_action_view(name, debug=debug)
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
            apio_index.call('register_api', self.spec)
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
        action_spec = self.actions._register_action_func(func)
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
            spec = apio_index.call('get_spec', name_or_url)
        api = RemoteAPI(spec)
        return api

class RemoteAPI(BaseAPI):

    def __init__(self, spec):
        self.spec = spec
        self.actions = RemoteAPI.ActionDispatcher(self)

    class ActionDispatcher(object):

        def __init__(self, api):
            self._api = api
            self._specs = api.spec['actions']
            # Needed for >>> from apio.cookbook.actions import *
            self.__all__ = []
            self.__funcs = {}
            for spec in self._specs:
                self.__all__.append(str(spec['name']))
                self.__funcs[spec['name']] = self._get_func(spec['name'])

        def _get_func(self, action_name):
            def func(obj=None):
                url = self._api.url + '/actions/' + action_name
                headers = { 'Content-Type': 'application/json' }
                res = requests.post(url, data=json.dumps(obj), headers=headers)
                if res.status_code != requests.codes.ok:
                    raise APIError(res.json['error'])
                return res.json
            return func

        def __getattr__(self, action_name):
            if action_name not in self.__all__:
                raise SpecError("Action %s is not defined" % action_name)
            return self.__funcs[action_name]

    @property
    def name(self):
        return self.spec['name']

    @property
    def url(self):
        return self.spec['url']

