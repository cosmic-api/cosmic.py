import json
from urllib2 import urlopen

from flask import Flask, Blueprint, Response, request, abort, make_response

from apio import types

class API(object):

    def __init__(self, name, url=None, client=None, homepage=None, **kwargs):
        if not client: client = Client()
        self.actions = {}
        self.client = client
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
    def get_blueprint(self):
        blueprint = Blueprint(self.spec['name'], __name__)
        for name, func in self.actions.items():
            @blueprint.route('/actions/%s' % name, methods=['POST'])
            def action():
                if not request.json:
                    abort(400)
                return json.dumps(func(request.json))
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
    def register_api(self, api):
        raise NotImplementedError()
    def get_api(self, api_name):
        raise NotImplementedError()
    def call_action(self, api_name, action_name, obj=None):
        raise NotImplementedError()
    def run(self, api, *args, **kwargs):
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(api.get_blueprint())
        app.run(*args, **kwargs)

class MockClient(object):
    apis = {}
    def register_api(self, api):
        name = api.spec['name']
        self.apis[name] = api
    def get_api(self, api_name):
        spec = self.apis[api_name].spec
        api = API(spec['name'], client=self)
        api.spec = spec
        return api
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


