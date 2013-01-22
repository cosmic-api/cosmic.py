from __future__ import unicode_literals

from apio.http import View, UrlRule, make_view

class Resource(object):

    def list(self, query):
        raise NotImplementedError()
    def get(self, id):
        raise NotImplementedError()
    def delete(self, id):
        raise NotImplementedError()
    def replace(self, id, data):
        raise NotImplementedError()
    def update(self, id, data):
        raise NotImplementedError()
    def create(self, data):
        raise NotImplementedError()

    def get_rules(self, debug=False):
        """Get a list of URL rules necessary for implementing this API

        :param debug:
            Will be passed into the :class:`apio.http.View`
            constructor of all the views in the app
        :returns:
            A list of :class:`apio.http.UrlRule` objects
        """

    def add_to_blueprint(self, blueprint, debug=False):
        name = self.__class__.name

        methods = ["GET", "DELETE", "POST"]
        @blueprint.route("/resources/%s/" % name, methods=methods)
        def bucket():
            if request.method == "GET":
                query = json.loads(request.args['query'])
                return self.list(query)
            if request.method == "POST":
                return self.create({})

        methods = ["GET", "DELETE", "PUT", "PATCH"]
        @blueprint.route("/resources/%s/<id>" % name, methods=methods)
        def single(id):
            if request.method == "GET":
                return self.get(id)
            if request.method == "DELETE":
                return self.delete(id)
            if request.method == "PUT":
                return self.replace(id, {})
            if request.method == "PATCH":
                return self.update(id, {})

