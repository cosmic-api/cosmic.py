from annopyte.annotations.signature import SignatureAnnotator
import inspect

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
    def action(self, *args, **kwargs):
        def decorator(func):
            if len(args) == 0:
                _return = types.Any()
            elif len(args) == 1:
                _return = args[0]
            elif len(args) == 2:
                _return = args[0]
                kwargs[inspect.getargspec(func)[0][0]] = args[1]
            else:
                raise Exception("Invalid action annotation")
            annotator = SignatureAnnotator(_return, **kwargs)
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
