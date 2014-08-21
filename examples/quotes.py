from cosmic.api import API
from cosmic.http import Server
from cosmic.types import *
from cosmic.models import BaseModel
from cosmic.exceptions import NotFound

quotes = API('quotes')

data = {
    "0": {"text": "Know thyself.", "author": "Socrates"},
    "1": {"text": "Never give up.", "author": "Shuzo Matsuoka"}
}

@quotes.model
class Quote(BaseModel):
    methods = ['get_by_id']
    properties = [
        required("text", String)
    ]
    @classmethod
    def get_by_id(cls, id):
        if id in data:
            return data[id]
        else:
            raise NotFound

wsgi_app = Server(words).wsgi_app

if __name__ == "__main__":
    words.run(use_reloader=True)
