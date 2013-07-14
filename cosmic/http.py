from __future__ import unicode_literals

import json
import requests
from requests.structures import CaseInsensitiveDict

from werkzeug.exceptions import HTTPException, InternalServerError, NotFound, abort
from werkzeug.urls import url_decode, url_encode
from werkzeug.datastructures import MultiDict

from flask import Flask, make_response
from flask import request
from teleport import Box, ValidationError

from .tools import *
from .exceptions import *
from . import cosmos


class RequestsPlugin(object):

    def __init__(self, base_url):
        self.base_url = base_url

    def __call__(self, url, **kwargs):
        return requests.request(url=self.base_url + url, **kwargs)

class WerkzeugTestClientPlugin(object):

    def __init__(self, client):
        self.client = client

    def __call__(self, url, **kwargs):
        r = self.client.open(path=url, **kwargs)
        resp = requests.Response()
        resp._content = r.data
        resp.headers = CaseInsensitiveDict(r.headers)
        resp.status_code = r.status_code
        return resp


class URLParams(ParametrizedWrapper):
    schema = String

    def __init__(self, param):
        if type(param) == list:
            param = OrderedDict(param)
        self.param = param

    def assemble(self, datum):
        # Use Werkzeug to turn URL params into a dict
        return self.from_multi_dict(url_decode(datum))

    def disassemble(self, datum):
        return url_encode(self.to_multi_dict(datum))

    def from_multi_dict(self, md):
        # Where only a single param was
        md = md.to_dict(flat=False)
        ret = {}
        for name, field in self.param.items():
            if name in md.keys():
                if not isinstance(field['schema'], Array) and len(md[name]) == 1:
                    ret[name] = json.loads(md[name][0])
                else:
                    ret[name] = []
                    for val in md[name]:
                        ret[name].append(json.loads(val))
        return Struct(self.param).from_json(ret)

    def to_multi_dict(self, datum):
        d = Struct(self.param).to_json(datum)
        md = MultiDict()
        for name, field in self.param.items():
            if name in d.keys():
                md[name] = []
                if isinstance(field['schema'], Array):
                    md[name] = map(json.dumps, d[name])
                else:
                    md[name] = json.dumps(d[name])
        return md




def error_response(message, code):
    body = json.dumps({"error": message})
    return make_response(body, code, {"Content-Type": "application/json"})

def err_to_response(err):
    is_remote = getattr(err, "remote", False)
    if isinstance(err, HTTPException) and not is_remote:
        if err.description != err.__class__.description:
            text = err.description
        else:
            text = err.name
        return error_response(text, err.code)
    elif isinstance(err, SpecError):
        return error_response(err.args[0], 400)
    elif isinstance(err, ValidationError):
        return error_response(str(err), 400)
    else:
        return error_response("Internal Server Error", 500)


class FlaskView(object):

    def __call__(self, *args, **kwargs):
        try:
            return make_response(self.handler(*args, **kwargs))
        except Exception as err:
            if self.debug:
                raise
            else:
                return err_to_response(err)


class FlaskViewAction(FlaskView):

    def __init__(self, view, debug):
        self.view = view
        self.debug = debug

    def handler(self):
        ct = request.headers.get('Content-Type', None)
        if request.method != "GET" and ct != "application/json":
            raise SpecError('Content-Type must be "application/json" got %s instead' % ct)
        try:
            request.payload = string_to_json(request.data)
        except ValueError:
            return error_response("Invalid JSON", 400)
        with cosmos:
            data = self.view(request.payload)
            if data == None:
                return ("", 204, {})
            else:
                if isinstance(data.datum, Box):
                    raise Exception(self.view)
                body = json.dumps(data.datum)
                return (body, 200, {"Content-Type": "application/json"})


class FlaskViewModelGetter(FlaskView):

    def __init__(self, model_cls, debug):
        self.model_cls = model_cls
        self.debug = debug

    def handler(self, id):
        with cosmos:
            model = self.model_cls.get_by_id(id)
            if model == None:
                raise NotFound
            body = json.dumps(self.model_cls.to_json(model))
            return make_response(body, 200, {"Content-Type": "application/json"})



class FlaskViewModelPutter(FlaskView):

    def __init__(self, model_cls, debug):
        self.model_cls = model_cls
        self.debug = debug

    def handler(self, id):
        with cosmos:
            model = self.model_cls.get_by_id(id)
            if model == None:
                raise NotFound
            try:
                request.payload = string_to_json(request.data)
            except ValueError:
                return error_response("Invalid JSON", 400)
            model = self.model_cls.from_json(request.payload.datum)
            model.save()
            return make_response("", 200, {"Content-Type": "application/json"})


class FlaskViewListGetter(FlaskView):

    def __init__(self, model_cls, debug):
        self.model_cls = model_cls
        self.debug = debug

    def handler(self):
        with cosmos:
            query = None
            self_link = "/%s" % self.model_cls.__name__

            if self.model_cls.query_fields != None:
                query_schema = URLParams(self.model_cls.query_fields)
                query = query_schema.from_multi_dict(request.args)
                if query:
                    self_link += "?" + query_schema.to_json(query)

            l = self.model_cls.get_list(**query)
            body = {
                "_links": {
                    "self": {"href": self_link}
                },
                "_embedded": {}
            }
            body["_embedded"][self.model_cls.__name__] = map(self.model_cls.to_json, l)
            return make_response(json.dumps(body), 200, {"Content-Type": "application/json"})


class ActionCallable(object):

    def __init__(self, function, url):
        self.function = function
        self.url = url

    def __call__(self, *args, **kwargs):
        packed = pack_action_arguments(*args, **kwargs)

        serialized = serialize_json(self.function.accepts, packed)

        data = json_to_string(serialized)

        headers = {'Content-Type': 'application/json'}
        res = requests.post(self.url, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            message = None
            if res.json and 'error' in res.json:
                message = res.json['error']
            try:
                abort(res.status_code, message)
            except Exception as e:
                # Flag the exception to specify that it came from a remote
                # API. If this exception bubbles up to the web layer, a
                # generic 500 response will be returned
                e.remote = True
                raise
        try:
            if self.function.returns and res.content != "":
                return self.function.returns.from_json(res.json)
            else:
                return None
        except ValidationError:
            e = InternalServerError("Call returned an invalid value")
            e.remote = True
            raise e


class ModelGetterCallable(object):

    def __init__(self, model_cls):
        self.model_cls = model_cls

    def __call__(self, id):
        url = "/%s/%s" % (self.model_cls.__name__, id)
        res = self.model_cls.api._request(url, method="GET", headers={"Content-Type": "application/json"})
        if res.status_code == 404:
            return None
        if res.status_code == 200:
            e = InternalServerError("Call returned an invalid value")
            e.remote = True
            if res.content == "":
                raise e
            try:
                return self.model_cls.schema.from_json(json.loads(res.content))
            except ValidationError:
                raise e
            except ValueError:
                raise e
        else:
            message = None
            if res.json and 'error' in res.json:
                message = res.json['error']
            try:
                abort(res.status_code, message)
            except Exception as e:
                # Flag the exception to specify that it came from a remote
                # API. If this exception bubbles up to the web layer, a
                # generic 500 response will be returned
                e.remote = True
                raise



class ModelPutterCallable(object):

    def __init__(self, model_cls):
        self.model_cls = model_cls

    def __call__(self, inst):
        url = "/%s/%s" % (self.model_cls.__name__, inst.id)
        body = json.dumps(self.model_cls.to_json(inst))
        res = self.model_cls.api._request(url, method="PUT", data=body, headers={"Content-Type": "application/json"})
        if res.status_code == 200:
            return
        else:
            message = None
            if res.json and 'error' in res.json:
                message = res.json['error']
            try:
                abort(res.status_code, message)
            except Exception as e:
                # Flag the exception to specify that it came from a remote
                # API. If this exception bubbles up to the web layer, a
                # generic 500 response will be returned
                e.remote = True
                raise



class ListGetterCallable(object):

    def __init__(self, model_cls):
        self.model_cls = model_cls

    def __call__(self, **query):

        url = "/%s" % self.model_cls.__name__

        if self.model_cls.query_fields != None:
            query_schema = URLParams(self.model_cls.query_fields)
            query_string = query_schema.to_json(query)
            if query_string:
                url += "?%s" % query_string

        res = self.model_cls.api._request(url=url, method="GET")
        if res.status_code == 200:
            e = InternalServerError("Call returned an invalid value")
            e.remote = True
            if res.content == "":
                raise e
            try:
                j = json.loads(res.content)
                return map(self.model_cls.from_json, j["_embedded"][self.model_cls.__name__])
            except (ValidationError, ValueError, KeyError):
                raise e
        else:
            message = None
            if res.json and 'error' in res.json:
                message = res.json['error']
            try:
                abort(res.status_code, message)
            except Exception as e:
                # Flag the exception to specify that it came from a remote
                # API. If this exception bubbles up to the web layer, a
                # generic 500 response will be returned
                e.remote = True
                raise
