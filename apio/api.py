import json
import requests

from flask import Flask, Blueprint, Response, request, abort, make_response

from apio import types

class API(object):

    def __init__(self, name=None, url=None, client=None, homepage=None, spec=None, **kwargs):
        if not client: client = Client()
        self.client = client
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
            if not request.json:
                abort(400)
            return json.dumps(func(request.json))
        return action_view
    def get_blueprint(self):
        blueprint = Blueprint(self.spec['name'], __name__)
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
            self.client.register_api(self)
        self.client.run(self, *args, **kwargs)
    def call(self, action_name, obj):
        if action_name in self.actions.keys():
            return self.actions[action_name](obj)
        else:
            return self.client.call_action(self.spec['name'], action_name, obj)
    @classmethod
    def load(cls, name, client=None):
        if not client: client = Client()
        return client.get_api(name)

class Client(object):
    # APIO index API
    index = None
    # API specs
    apis = {}
    def __init__(self):
        # Bootstrap the client
        res = requests.post("http://api.apio.io/actions/get_spec", data=json.dumps("apio-index"))
        self.index = API('apio-index', client=self)
        self.index.spec = res.json
        self.apis['apio-index'] = self.index
    def get_spec(self, api_name):
        return self.index.call('get_spec', api_name)
    def register_api(self, api):
        return self.index.call('register_api', api.spec)
    def get_api(self, api_name):
        api = API(spec=self.get_spec(api_name), client=self)
        self.apis[api_name] = api
        return api
    def call_action(self, api_name, action_name, obj=None):
        url = self.apis[api_name].spec['url'] + '/actions/' + action_name
        res = requests.post(url, data=json.dumps(obj))
        return res.json
    def run(self, api, *args, **kwargs):
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(api.get_blueprint())
        app.run(*args, **kwargs)

class MockClient(object):
    apis = {}
    def register_api(self, api):
        self.apis[api.spec['name']] = api
        return True
    def get_spec(self, api_name):
        return self.apis[api_name].spec
    def get_api(self, api_name):
        spec = self.get_spec(api_name)
        return API(spec=spec, client=self)
    def call_action(self, api_name, action_name, obj=None):
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.apis[api_name].get_blueprint())
        werkzeug_client = app.test_client()
        url = "/actions/%s" % action_name
        data = json.dumps(obj)
        res = werkzeug_client.post(url, data=data, content_type="application/json", method="POST")
        return json.loads(res.data)
    # We don't want any real HTTP action during testing
    def run(self, api):
        pass


