from cosmic.api import API
from cosmic.types import *
from cosmic.models import BaseModel
from cosmic.exceptions import NotFound

words = API('words')


@words.action(accepts=String, returns=String)
def pluralize(word):
    if word.endswith('y'):
        return word[:-1] + 'ies'
    else:
        return word + 's'


@words.model
class Word(BaseModel):
    methods = ['get_by_id']
    properties = [
        required(u"letters", String)
    ]
    @classmethod
    def get_by_id(cls, id):
        if id == "0":
            return {"letters": "hello"}
        else:
            raise NotFound

if __name__ == "__main__":
    words.run(use_reloader=True)
