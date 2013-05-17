from __future__ import unicode_literals

from werkzeug.local import release_local
from werkzeug.wrappers import Request as WerkzeugRequest
from flask import Flask, make_response
from flask import request as flask_request
from teleport import ValidationError

from .tools import json_to_string
from .http import Request, JSONRequest, Response
from .exceptions import *
from . import request as cosmic_request


class FlaskView(object):

    def __init__(self, view):
        self.view = view

    def normalize_request(self, req):
        headers = req.headers
        method = req.method
        body = req.data
        req = Request(method, body, headers)
        return JSONRequest(req)

    def make_response(self, resp):
        return make_response(resp.body, resp.code, resp.headers)

    def __call__(self, *args, **kwargs):
        req = self.normalize_request(flask_request)
        with req:
            res = self.view(req)
            return self.make_response(res)



class FlaskPlugin(object):

    def __init__(self, setup_func, url_prefix="", debug=False, werkzeug_map=None):
        self.setup_func = setup_func
        self.app = Flask(__name__, static_folder=None)
        self.debug = debug
        for rule in werkzeug_map.iter_rules():

            v = self.make_view(rule.endpoint)

            url = url_prefix + rule.rule
            self.app.add_url_rule(url,
                view_func=FlaskView(v),
                methods=rule.methods,
                endpoint=rule.endpoint.__name__)

    def make_view(self, func):
        def view(*args, **kwargs):
            req = cosmic_request
            res = Response(200)
            # Necessary for CORS
            if "Origin" in req.headers:
                res.headers["Access-Control-Allow-Origin"] = req.headers["Origin"]
            # Catch ClientErrors and APIErrors and turn them into Responses
            try:
                try:
                    req.context = self.setup_func(req.headers)
                    data = func(req.payload)
                    if data != None:
                        res.body = json.dumps(data.datum)
                    return res
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
                    if self.debug:
                        raise
                    raise APIError("Internal Server Error")
            except HttpError as err:
                return err.get_response()
        return view

    """
    def middleware(self, app):
        def wrapped(environ, start_response):
            flask_request = Request(environ)
            cosmic_request = self.normalize_request(flask_request)

            cosmic_response = app(cosmic_request, debug=self.debug)
            flask_response = self.make_flask_response(cosmic_response)
            return flask_response(environ, start_response)
        return wrapped

    def wsgi_app(self, environ, start_response):
        werkzeug_request = WerkzeugRequest(environ)
        cosmic_request = self.normalize_request(werkzeug_request)

        # Authenticate the user, make local context
        try:
            cosmic_request.context = self.setup_func(cosmic_request.headers)
        except AuthenticationError as e:
            return self.make_flask_response(e.get_response())

        with cosmic_request:

            cosmic_response = view(cosmic_request, debug=self.debug)
            flask_response = self.make_flask_response(cosmic_response)

            return flask_response(environ, start_response)
    """

