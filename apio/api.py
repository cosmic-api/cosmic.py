from apio import types

class API(object):
    def __init__(self, name, url, **kwargs):
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

class Model(object):
    def __init__(self, name, schema):
        self.name = name
        self.schema = schema
