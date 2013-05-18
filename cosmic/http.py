from __future__ import unicode_literals

import json

from werkzeug.local import LocalProxy, LocalStack, release_local
from werkzeug.exceptions import HTTPException, Unauthorized, BadRequest, InternalServerError
from flask import Flask, Blueprint, make_response, request
from teleport import Box, ValidationError

from .tools import json_to_string, string_to_json
from .exceptions import *
from .wrappers import Request


class FlaskPlugin(object):

    def __init__(self, setup_func, url_prefix=None, debug=False, werkzeug_map=None):
        self.setup_func = setup_func

        self.blueprint = Blueprint('cosmic', __name__)
        self.blueprint.before_request(self.before_request)

        self.blueprint.errorhandler(SpecError)(self.handle_cosmic_error)
        self.blueprint.errorhandler(ValidationError)(self.handle_validation_error)
        self.blueprint.errorhandler(401)(self.handle_http_error)

        self.debug = debug
        for rule in werkzeug_map.iter_rules():

            v = self.make_view(rule.endpoint)

            self.blueprint.add_url_rule(rule.rule,
                view_func=v,
                methods=rule.methods,
                endpoint=rule.endpoint.__name__)

        self.app = Flask(__name__, static_folder=None)
        self.app.debug = debug
        self.app.request_class = Request
        self.app.register_blueprint(self.blueprint, url_prefix=url_prefix)

    def handle_http_error(self, e):
        if e.description != e.__class__.description:
            text = e.description
        else:
            text = e.name
        body = json.dumps({"error": text})
        return make_response(body, e.code, {})

    def handle_cosmic_error(self, e):
        body = json.dumps({"error": e.args[0]})
        return make_response(body, e.code, {})

    def handle_validation_error(self, e):
        body = json.dumps({"error": str(e)})
        return make_response(body, 400, {})

    def before_request(self):
        # Trigger the evaluation of properties, possibly raising exceptions
        request.json_payload
        request.context = self.setup_func(request.headers)

    def make_view(self, func):
        def view(*args, **kwargs):
            data = func(request.json_payload)
            body = ""
            if data != None:
                body = json.dumps(data.datum)
            return make_response(body)
        return view
