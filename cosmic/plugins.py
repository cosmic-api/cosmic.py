from __future__ import unicode_literals

from werkzeug.local import release_local
from flask import Flask, Blueprint, request, make_response
from teleport import ValidationError

from .tools import json_to_string
from .http import Request, JSONRequest, Response
from .exceptions import *




class FlaskPlugin(object):

    def __init__(self, setup_func, url_prefix=None, debug=False, werkzeug_map=None):
        self.setup_func = setup_func
        self.app = Flask(__name__, static_folder=None)
        self.debug = debug
        self.blueprint = Blueprint('API', __name__)
        for rule in werkzeug_map.iter_rules():
            flask_view = self.make_flask_view(rule.endpoint)
            flask_view.__name__ = str(rule.endpoint.__name__)
            self.blueprint.add_url_rule(rule.rule, view_func=flask_view, methods=rule.methods)
        self.app.register_blueprint(self.blueprint, url_prefix=url_prefix)

    def make_flask_view(self, view):
        def flask_view(*args, **kwargs):
            req = self.normalize_request(request)

            # Authenticate the user, make local context
            try:
                req.context = self.setup_func(req.headers)
            except AuthenticationError as e:
                return self.make_flask_response(e.get_response())

            with req:

                res = Response(200)
                # Necessary for CORS
                if "Origin" in req.headers:
                    res.headers["Access-Control-Allow-Origin"] = req.headers["Origin"]
                # Catch ClientErrors and APIErrors and turn them into Responses
                try:
                    # Validate request
                    try:
                        req = JSONRequest(req)
                        data = view(req.payload)
                        if data != None:
                            res.body = json.dumps(data.datum)
                        return self.make_flask_response(res)
                    except HttpError:
                        raise
                    except JSONParseError:
                        raise ClientError("Invalid JSON")
                    except SpecError as err:
                        raise ClientError(err.args[0])
                    except ValidationError as e:
                        raise ClientError(str(e))
                    # Any other exception should be handled gracefully
                    except:
                        if debug:
                            raise
                        raise APIError("Internal Server Error")
                except HttpError as err:
                    return self.make_flask_response(err.get_response())

        return flask_view

    def normalize_request(self, req):
        headers = req.headers
        method = req.method
        body = req.data
        return Request(method, body, headers)

    def make_flask_response(self, resp):
        return make_response(resp.body, resp.code, resp.headers)

    def middleware(self, app):
        def wrapped(environ, start_response):
            flask_request = Request(environ)
            cosmic_request = self.normalize_request(flask_request)

            cosmic_response = app(cosmic_request, debug=self.debug)
            flask_response = self.make_flask_response(cosmic_response)
            return flask_response(environ, start_response)
        return wrapped

    def wsgi_app(self, environ, start_response):
        flask_request = Request(environ)
        cosmic_request = self.normalize_request(flask_request)

        # Authenticate the user, make local context
        try:
            cosmic_request.context = self.setup_func(cosmic_request.headers)
        except AuthenticationError as e:
            return self.make_flask_response(e.get_response())

        with cosmic_request:

            cosmic_response = view(cosmic_request, debug=self.debug)
            flask_response = self.make_flask_response(cosmic_response)

            return flask_response(environ, start_response)

