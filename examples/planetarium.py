from cosmic import cosmos
from cosmic.api import API
from cosmic.models import Model
from teleport import *


planets = [
    {
        u"name": u"Sun",
        u"_links": {
            u"self": {u"href": u"/Sphere/0"},
        }
    },
    {
        u"name": u"Earth",
        u"_links": {
            u"self": {u"href": u"/Sphere/1"},
            u"revolves_around": {u"href": u"/Sphere/0"},
        }
    },
    {
        u"name": u"Moon",
        u"_links": {
            u"self": {u"href": u"/Sphere/2"},
            u"revolves_around": {u"href": u"/Sphere/1"},
        }
    }
]

planetarium = API("planetarium")

@planetarium.model
class Sphere(Model):
    properties = [
        required("name", String)
    ]
    links = [
        optional("revolves_around", cosmos.M('planetarium.Sphere'))
    ]
    query_fields = [
        optional("name", String),
        optional("revolves_around", String)
    ]



if __name__ == "__main__":
    planetarium.run()
