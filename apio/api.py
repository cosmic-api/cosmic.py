from annopyte.annotations.signature import SignatureAnnotator, _NO_VALUE

cache = dict()

class API(object):
    def __init__(self, name, url, **kwargs):
        self.name = name
        self.url = url
        self.homepage = kwargs.get('homepage')
        self.models = {}
        self.actions = {}
    def serialize(self):
        spec = {
            "name": self.name,
            "url": self.url,
            "actions": {}
        }
        if self.homepage:
            spec['homepage'] = self.homepage
        for name, func in self.actions.items():
            action = {
                "accepts": {
                    "type": "object",
                    "properties": {}
                }
            }
            for arg, arg_type in func.__annotations__.items():
                if arg == "return":
                    action["returns"] = arg_type.serialize()
                else:
                    action["accepts"]["properties"][arg] = arg_type.serialize()
            spec['actions'][name] = action
        return spec
    def action(self, _return=_NO_VALUE, **kwargs):
        annotator = SignatureAnnotator(_return, **kwargs)
        def decorator(func):
            annotated = annotator(func)
            self.actions[func.__name__] = annotated
            return annotated
        return decorator

class Model(object):
    def __init__(self, name, schema):
        self.name = name
        self.schema = schema
