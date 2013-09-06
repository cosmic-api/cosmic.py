from cosmic import cosmos
from cosmic.api import API
from cosmic.testing import DBModel, DBContext
from teleport import *


planet_db = {
    "spheres": [
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
}

def make_planetarium():

    planetarium = API("planetarium")


    @planetarium.model
    class Sphere(DBModel):
        db_table = "spheres"

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

        @classmethod
        def validate(cls, datum):
            if datum["name"][0].islower():
                raise ValidationError("Name must be capitalized", datum["name"])

    @planetarium.action(accepts=cosmos.M('planetarium.Sphere'), returns=String)
    def hello(sphere):
        return "Hello, %s" % sphere.name

    return planetarium


if __name__ == "__main__":
    with DBContext(planet_db):
        make_planetarium().run()
