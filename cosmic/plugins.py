from __future__ import unicode_literals

from werkzeug.local import release_local
from flask import Flask, Blueprint, request, make_response

from cosmic import context
from cosmic.http import Request
from cosmic.exceptions import ClientError, AuthenticationError


class FlaskPlugin(object):

    def __init__(self, rules, setup_func, url_prefix=None, debug=False):
        self.rules = rules
        self.setup_func = setup_func
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
            try:
                # Authenticate the user, make local context
                release_local(context)
                for key, value in self.setup_func(headers).items():
                    setattr(context, key, value)
            except AuthenticationError as e:
                return self.make_flask_response(e.get_response())
            req = Request(method, body, headers)
            resp = view(req, debug=self.debug)
            return self.make_flask_response(resp)
        return flask_view

    def make_flask_response(self, resp):
        return make_response(resp.body, resp.code, resp.headers)
