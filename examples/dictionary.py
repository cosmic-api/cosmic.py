import random

from collections import OrderedDict

from cosmic.api import API
from cosmic.testing import DBModel
from cosmic.models import LazyWrapper
from teleport import *


langdb = {
    "languages": [
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
    ],
    "words": [
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
}


dictionary = API("dictionary")

@dictionary.model
class Language(DBModel):
    db_table = 'languages'
    properties = [
        required("code", String)
    ]
    query_fields = [
        optional("code", String)
    ]
    sets = [
        ("words", {"model": LazyWrapper("dictionary.Word")})
    ]




@dictionary.model
class Word(DBModel):
    db_table = 'words'
    properties = [
        required("text", String)
    ]
    links = [
        required("language", Language)
    ]


if __name__ == "__main__":
    dictionary.run()
