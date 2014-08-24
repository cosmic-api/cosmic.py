import datetime

from cosmic.api import API
from cosmic.exceptions import HTTPError
from cosmic.testing import DBModel, db
from cosmic.types import *
from cosmic.http import Server


planet_db = {
    "Sphere": {
        "0": {
            u"name": u"Sun",
            u"temperature": 3000.0,
        },
        "1": {
            u"name": u"Earth",
            u"temperature": 30.0,
            u"revolves_around": "0",
        },
        "2": {
            u"name": u"Moon",
            u"temperature": -50.0,
            u"revolves_around": "1",
        },
    }
}

planetarium = API("planetarium")


class PlanetariumServer(Server):
    def parse_request(self, endpoint, request, **url_args):
        if request.headers.get('X-Danish', None) != "poppyseed":
            raise HTTPError(401, "Unauthorized")
        return super(PlanetariumServer, self).parse_request(endpoint, request, **url_args)


planetarium_server = PlanetariumServer(planetarium)


@planetarium.model
class Sphere(DBModel):
    table_name = 'Sphere'
    methods = ["get_list", "get_by_id", "create", "update", "delete"]

    properties = [
        required("name", String),
        required("temperature", Float),
    ]
    links = [
        optional_link("revolves_around", Model('planetarium.Sphere')),
    ]
    query_fields = [
        optional("name", String),
        optional("revolves_around", String)
    ]
    list_metadata = [
        required('last_updated', DateTime)
    ]

    @classmethod
    def get_list(cls, **kwargs):
        l = super(Sphere, cls).get_list(**kwargs)
        metadata = {
            'last_updated': datetime.datetime(year=2014, month=1, day=1)
        }
        return (l, metadata)

    @classmethod
    def validate_patch(cls, datum):
        if 'temperature' in datum:
            raise ValidationError("Temperature is readonly")
        if "name" not in datum:
            raise ValidationError("Name is required")
        if datum["name"][0].islower():
            raise ValidationError("Name must be capitalized", datum["name"])

    @classmethod
    def create(cls, **patch):
        return super(Sphere, cls).create(temperature=60, **patch)


@planetarium.action(accepts=Representation(Model('planetarium.Sphere')), returns=String)
def hello(sphere):
    return "Hello, %s" % sphere[1]['name']


if __name__ == "__main__":
    with db.swap(planet_db):
        planetarium.run()
