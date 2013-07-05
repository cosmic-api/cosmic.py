import random

from collections import OrderedDict

from cosmic.api import API
from cosmic.models import Model
from teleport import *

dictionary = API("dictionary")

languages = [
    {
        u"_data": u"en",
        u"_links": {
            u"self": {u"href": u"/Language/0"},
        }
    },
    {
        u"_data": u"eo",
        u"_links": {
            u"self": {u"href": u"/Language/1"},
        }
    }
]
words = [
    {
        u"_data": u"dog",
        u"_links": {
            u"self": {u"href": u"/Word/0"},
            u"language": {u"href": u"/Language/0"}
        }
    },
    {
        u"_data": u"hundo",
        u"_links": {
            u"self": {u"href": u"/Word/1"},
            u"language": {u"href": u"/Language/1"}
        }
    }
]

@dictionary.model
class Language(Model):
    data_schema = String
    query_fields = [
        optional("code", String)
    ]

    @classmethod
    def get_list(cls, code=None):
        if code == None:
            return map(cls.from_json, languages)
        elif code == "en":
            return [cls.from_json(languages[0])]
        elif code == "eo":
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
    data_schema = String
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
