import json
import requests

from flask import Flask, Blueprint, Response, request, abort, make_response

from apio import types

# API objects
apis = {}

def ensure_bootstrapped():
    if 'apio-index' not in apis.keys():
        res = requests.post("http://api.apio.io/actions/get_spec", data=json.dumps("apio-index"))
        index = API('apio-index')
        index.spec = res.json['data']
        apis['apio-index'] = index

class APIError(Exception):
    def __init__(self, message, http_code=500):
        self.message = message
        self.http_code = http_code

class API(object):

    def __init__(self, name=None, url=None, homepage=None, spec=None, **kwargs):
        self.actions = {}
        if spec:
            self.spec = spec
        else:
            self.spec = {
                "actions": {},
                "name": name,
                "url": url
            }
            if homepage:
                self.spec['homepage'] = homepage
    @property
    def name(self):
        return self.spec['name']
    def serialize(self):
        return self.spec
    def action(self):
        def decorator(func):
            action = {
                "accepts": {
                    "type": "any"
                },
                "returns": {
                    "type": "any"
                }
            }
            self.spec['actions'][func.__name__] = action
            self.actions[func.__name__] = func
            return func
        return decorator
    def _get_action_view(self, name):
        func = self.actions[name]
        def action_view():
            if request.json == None:
                return json.dumps({
                    "error": "Bad request"
                }), 400
            try:
                data = func(request.json)
            # If the user threw an APIError
            except APIError as err:
                return json.dumps({
                    "error": err.message
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
        blueprint = Blueprint(self.name, __name__)
        for name in self.actions.keys():
            # If enpoint isn't specified unique, Flask confuses the actions by assuming
            # that all endpoints are named 'action'
            func = self._get_action_view(name)
            blueprint.add_url_rule('/actions/%s' % name, name, func, methods=['POST'])
        @blueprint.route('/spec.json')
        def getspec():
            spec = json.dumps(self.serialize())
            return Response(spec, mimetype="application/json")
        return blueprint
    def run(self, *args, **kwargs):
        if kwargs.pop('register_api', True):
            ensure_bootstrapped()
            apis['apio-index'].call('register_api', self.spec)
        if 'dry_run' in kwargs.keys(): return
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.get_blueprint())
        app.run(*args, **kwargs)
    def call(self, action_name, obj):
        if action_name in self.actions.keys():
            return self.actions[action_name](obj)
        else:
            url = self.spec['url'] + '/actions/' + action_name
            res = requests.post(url, data=json.dumps(obj))
            if 'error' in res.json:
                raise APIError(res.json['error'])
            return res.json['data']
    @classmethod
    def load(cls, api_name):
        ensure_bootstrapped()
        spec = apis['apio-index'].call('get_spec', api_name)
        api = API(spec=spec)
        apis[api_name] = api
        return api

