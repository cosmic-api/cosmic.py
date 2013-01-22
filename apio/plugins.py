from __future__ import unicode_literals

from flask import Flask, Blueprint, request, make_response

from apio.http import Request
from apio.exceptions import ClientError


class FlaskPlugin(object):

    def __init__(self, rules, url_prefix=None, debug=False):
        self.rules = rules
        self.app = Flask(__name__, static_folder=None)
        self.debug = debug
        self.blueprint = Blueprint('API', __name__)
        for rule in self.rules:
            flask_view = self.make_flask_view(rule.view)
            self.blueprint.add_url_rule(rule.url, rule.name, flask_view, methods=[rule.view.method])
        self.app.register_blueprint(self.blueprint, url_prefix=url_prefix)

    def make_flask_view(self, view):
        def flask_view(*args, **kwargs):
            headers = request.headers
            method = request.method
            body = request.data
            req = Request(method, body, headers)
            r = view(req, debug=self.debug)
            return make_response(r.body, r.code, r.headers)
        return flask_view
