__version__ = "0.0.1"

cache = dict()

class API(object):
    def __init__(self, name, url, **kwargs):
        self.name = name
        self.url = url
        self.homepage = kwargs.get('homepage')
        self.models = {}
    def serialize(self):
        spec = {
            "name": self.name,
            "url": self.url,
        }
        if self.homepage:
            spec['homepage'] = self.homepage
        return spec

class Model(object):
    def __init__(self, name, schema):
        self.name = name
        self.schema = schema

apis = {"facebook":1, "twitter":2}

locals = lambda: {"facebook":2}
