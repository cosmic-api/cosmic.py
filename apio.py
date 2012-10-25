__version__ = "0.0.1"

api_schema = {
    "type": "object",
    "name": {
        "type": "string"
    },
    "url": {
        "type": "string"
    },
    "homepage": {
        "type": "string"
    },
    "models": {
        "type": "object"
    }
}

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

