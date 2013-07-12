import random

from collections import OrderedDict

from cosmic.api import API
from cosmic.models import Model
from teleport import *

dictionary = API("dictionary")

languages = [
    {
        u"code": u"en",
        u"_links": {
            u"self": {u"href": u"/Language/0"},
        }
    },
    {
        u"code": u"eo",
        u"_links": {
            u"self": {u"href": u"/Language/1"},
        }
    }
]
words = [
    {
        u"text": u"dog",
        u"_links": {
            u"self": {u"href": u"/Word/0"},
            u"language": {u"href": u"/Language/0"}
        }
    },
    {
        u"text": u"hundo",
        u"_links": {
            u"self": {u"href": u"/Word/1"},
            u"language": {u"href": u"/Language/1"}
        }
    }
]

class DBModel(Model):

    @classmethod
    def get_by_id(cls, id):
        try:
            return cls.from_json(cls.db_table[int(id)])
        except IndexError:
            return None

    @classmethod
    def get_list(cls, **kwargs):
        if not kwargs:
            return map(cls.from_json, cls.db_table)
        ret = []
        for row in cls.db_table:
            if row != None:
                keep = True
                for key, val in kwargs.items():
                    if row[key] != val:
                        keep = False
                        break
                if keep:
                    ret.append(cls.from_json(row))
        return ret

    def save(self):
        cls.db_table[int(self.id)] = cls.to_json(self)

    def delete(self):
        cls.db_table[int(self.id)] = None


@dictionary.model
class Language(DBModel):
    db_table = languages
    properties = [
        required("code", String)
    ]
    query_fields = [
        optional("code", String)
    ]


@dictionary.model
class Word(DBModel):
    db_table = words
    properties = [
        required("text", String)
    ]
    links = [
        required("language", Language)
    ]


if __name__ == "__main__":
    dictionary.run()
