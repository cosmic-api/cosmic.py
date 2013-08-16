from cosmic import cosmos
from cosmic.api import API
from cosmic.testing import DBModel
from cosmic.models import Cosmos
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

def make_dictionary():

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


    @dictionary.model
    class Word(DBModel):
        db_table = 'words'
        properties = [
            required("text", String)
        ]
        links = [
            required("language", Language)
        ]
        query_fields = []

    return dictionary


if __name__ == "__main__":
    with Cosmos():
        dictionary.run()
