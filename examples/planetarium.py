from cosmic import cosmos
from cosmic.models import M
from cosmic.api import API
from cosmic.testing import DBModel, DBContext
from teleport import *

from werkzeug.local import LocalProxy

from flask import abort


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

    @planetarium.authenticate
    def authenticate(headers):
        danish = headers.get('X-Danish', None)
        if danish != "poppyseed":
            abort(401)

    @planetarium.model
    class Sphere(DBModel):
        db_table = "spheres"

        properties = [
            required("name", String)
        ]
        links = [
            optional("revolves_around", M('planetarium.Sphere'))
        ]
        query_fields = [
            optional("name", String),
            optional("revolves_around", String)
        ]

        @classmethod
        def validate(cls, datum):
            if datum["name"][0].islower():
                raise ValidationError("Name must be capitalized", datum["name"])


    @planetarium.action(accepts=M('planetarium.Sphere'), returns=String)
    def hello(sphere):
        return "Hello, %s" % sphere.name

    return planetarium

if __name__ == "__main__":
    with DBContext(planet_db):
        make_planetarium().run()
