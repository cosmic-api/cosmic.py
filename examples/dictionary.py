import random

from collections import OrderedDict

from cosmic.api import API
from cosmic.models import Model
from teleport import *

dictionary = API("dictionary")

languages = [
    {
        u"_links": {},
        u"_data": u"en"
    },
    {
        u"_links": {},
        u"_data": u"eo"
    }
]
words = [
    {
        u"_data": u"dog",
        u"_links": {
            u"language": {u"href": u"/languages/0"}
        }
    },
    {
        u"_data": u"hundo",
        u"_links": {
            u"language": {u"href": u"/languages/1"}
        }
    }
]

@dictionary.model
class Language(Model):
    schema = String
    collection = "languages"
    query_fields = [
        optional("code", String)
    ]

    @classmethod
    def get_list(cls, query):
        if query == {}:
            return map(cls.from_json, languages)
        elif query['code'] == "en":
            return [cls.from_json(languages[0])]
        elif query['code'] == "eo":
            return [cls.from_json(languages[1])]
        else:
            return []

    @classmethod
    def get_by_id(cls, id):
        try:
            return cls.from_json(languages[int(id)])
        except IndexError:
            return None

@dictionary.model
class Word(Model):
    schema = String
    collection = "words"

    links = OrderedDict([
        required("language", Language)
    ])

    @classmethod
    def get_by_id(cls, id):
        try:
            return cls.from_json(words[int(id)])
        except IndexError:
            return None

if __name__ == "__main__":
    dictionary.run()
