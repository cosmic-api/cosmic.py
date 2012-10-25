__version__ = "0.0.1"

api_schema = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "required": True
        },
        "url": {
            "type": "string",
            "required": True
        },
        "homepage": {
            "type": "string"
        },
        "models": {
            "type": "object",
            "patternProperties": {
                r'^[a-zA-Z0-9_]+$': {}
            }
        }
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

