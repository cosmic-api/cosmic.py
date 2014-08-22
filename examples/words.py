from time import sleep

from cosmic.api import API
from cosmic.http import Server
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

@words.action(accepts=Integer)
def lock_thread(seconds):
    sleep(seconds)

@words.action(accepts=Representation(Model('words.Word')), returns=Integer)
def count_letters(word):
    return len(word[1]['letters'])

wsgi_app = Server(words).wsgi_app

if __name__ == "__main__":
    words.run(use_reloader=True)
