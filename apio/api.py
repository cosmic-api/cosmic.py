import json
import requests
import inspect

from flask import Flask, Blueprint, Response, request, abort, make_response

from apio import types

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
        "models": {
            "type": "object",
            "patternProperties": {
                r'^[a-zA-Z0-9_]+$': {
                    "$ref": "http://json-schema.org/draft-03/schema#"
                }
            }
        },
        "actions": {
            "type": "object",
            "patternProperties": {
                r'^[a-zA-Z0-9_]+$': {
                    "type": "object",
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

# API objects
apis = {}

def ensure_bootstrapped():
    """Ensures the APIO index API is loaded. Call this before trying API.load"""
    if 'apio-index' not in apis.keys():
        data = json.dumps("apio-index")
        res = requests.post("http://api.apio.io/actions/get_spec", data=data)
        index = RemoteAPI('apio-index')
        index.spec = res.json['data']
        apis['apio-index'] = index

class APIError(Exception):
    def __init__(self, message, http_code=500):
        self.args = [message]
        self.http_code = http_code

class BaseAPI(object):
    def __init__(self, spec):
        self.spec = spec
    @property
    def name(self):
        return self.spec['name']


class API(BaseAPI):

    def __init__(self, name=None, url=None, homepage=None, **kwargs):
        self.actions = {}
        spec = {
            "actions": {},
            "name": name,
            "url": url
        }
        if homepage: spec['homepage'] = homepage
        super(API, self).__init__(spec)

    def call(self, action_name, obj=None):
        # If it's a no argument function, don't pass in anything to avoid error
        if self.spec['actions'][action_name]["accepts"]["type"] == "null":
            return self.actions[action_name]()
        return self.actions[action_name](obj)

    def _get_action_view(self, action_name):
        """Wraps a user-defined action function to return a Flask view function
        that handles errors and returns proper HTTP responses"""
        def action_view():
            if request.headers.get('Content-Type', None) != "application/json":
                return json.dumps({
                    "error": 'Content-Type must be "application/json"'
                }), 400
            if request.json == None:
                return json.dumps({
                    "error": "Bad request"
                }), 400
            try:
                data = self.call(action_name, request.json)
            # If the user threw an APIError
            except APIError as err:
                return json.dumps({
                    "error": err.args[0]
                }), err.http_code
            # Any other exception should be handled gracefully
            except:
                return json.dumps({
                    "error": "Internal Server Error"
                }), 500
            return json.dumps({
                "data": data
            })
        return action_view

    def get_blueprint(self):
        """Returns a Flask Blueprint object with all of the API's routes set up.
        Use this if you want to integrate your API into a Flask application.
        """
        blueprint = Blueprint(self.name, __name__)
        for name, func in self.actions.items():
            view = self._get_action_view(name)
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

        if kwargs.pop('register_api', True):
            ensure_bootstrapped()
            apis['apio-index'].call('register_api', self.spec)
        if 'dry_run' in kwargs.keys(): return
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.get_blueprint())
        app.run(*args, **kwargs)

    def action(self):
        """Registers the given function as an API action. To be used as a 
        decorator.
        """
        def decorator(func):
            action = {
                "returns": {
                    "type": "any"
                }
            }
            # If provided function has no arguments, note it in the spec
            argspec = inspect.getargspec(func)
            args = argspec[0]
            if len(args) == 0:
                action["accepts"] = { "type": "null" }
            else:
                action["accepts"] = { "type": "any" }
            self.spec['actions'][func.__name__] = action
            self.actions[func.__name__] = func
            return func
        return decorator

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
            spec = apis['apio-index'].call('get_spec', name_or_url)
        api = RemoteAPI(spec)
        apis[name_or_url] = api
        return api

class RemoteAPI(BaseAPI):
    def call(self, action_name, obj=None):
        url = self.spec['url'] + '/actions/' + action_name
        res = requests.post(url, data=json.dumps(obj))
        if 'error' in res.json:
            raise APIError(res.json['error'])
        return res.json['data']

