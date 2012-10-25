__version__ = "0.0.1"

import json

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
    }
}

class API(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.url = kwargs.get('url')
        self.homepage = kwargs.get('url')
    def serialize(self):
        return json.stringify({
            "name": self.name,
            "url": self.url,
            "homepage": self.homepage
        })
