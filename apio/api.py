from annopyte.annotations.signature import SignatureAnnotator
from apio import types

cache = dict()

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
    def action(self, _return=types.Any(), **kwargs):
        annotator = SignatureAnnotator(_return, **kwargs)
        def decorator(func):
            annotated = annotator(func)
            action = {
                "accepts": {
                    "type": "object",
                    "properties": {}
                }
            }
            for arg, arg_type in annotated.__annotations__.items():
                if arg == "return":
                    action["returns"] = arg_type.serialize()
                else:
                    action["accepts"]["properties"][arg] = arg_type.serialize()
            self.spec['actions'][func.__name__] = action
            self.actions[func.__name__] = annotated
            return annotated
        return decorator

class Model(object):
    def __init__(self, name, schema):
        self.name = name
        self.schema = schema
