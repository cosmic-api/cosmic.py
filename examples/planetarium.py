from cosmic import cosmos
from cosmic.models import M
from cosmic.api import API
from cosmic.testing import DBModel, DBContext
from cosmic.types import *
from cosmic.http import ServerHook

from werkzeug.local import LocalProxy

from flask import abort


planet_db = {
    "Sphere": [
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


planetarium = API("planetarium")


class SHook(ServerHook):

    def parse_request(self, endpoint, request, **url_args):
        if not endpoint.never_authenticate:
            if request.headers.get('X-Danish', None) != "poppyseed":
                abort(401)
        return super(SHook, self).parse_request(endpoint, request, **url_args)

planetarium.server_hook = SHook()


@planetarium.model
class Sphere(DBModel):

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


if __name__ == "__main__":
    with DBContext(planet_db):
        planetarium.run()
