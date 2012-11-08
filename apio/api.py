from apio import types
from flask import Blueprint

class API(object):
    def __init__(self, name, url=None, **kwargs):
        self.models = {}
        self.actions = {}
        self.spec = {
            "actions": {},
            "name": name,
            "url": url
        }
        if 'homepage' in kwargs:
            self.spec['homepage'] = kwargs['homepage']
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
            @blueprint.route('/actions/%s' % name)
            def action(*args, **kwargs):
                return func(*args, **kwargs)
        return blueprint
    def run(self, *args, **kwargs):
        from flask import Flask
        app = Flask(__name__, static_folder=None)
        app.register_blueprint(self.get_blueprint())
        app.run(*args, **kwargs)


class Model(object):
    def __init__(self, name, schema):
        self.name = name
        self.schema = schema
