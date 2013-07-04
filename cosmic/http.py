from __future__ import unicode_literals

import json
import requests

from werkzeug.exceptions import HTTPException, InternalServerError, NotFound, abort
from werkzeug.urls import url_decode

from flask import Flask, make_response
from flask import request
from teleport import Box, ValidationError

from .tools import *
from .exceptions import *
from . import cosmos


class URLParams(ParametrizedWrapper):
    schema = String

    def __init__(self, param):
        if type(param) == list:
            param = OrderedDict(param)
        self.param = param

    def assemble(self, datum):
        # Use Werkzeug to turn URL params into a dict
        return self.from_multi_dict(url_decode(datum))

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

    def disassemble(self, datum):
        raise NotImplementedError()



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
            return self.handler(*args, **kwargs)
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
            body = ""
            if data != None:
                body = json.dumps(data.datum)
            return make_response(body, 200, {"Content-Type": "application/json"})


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


class FlaskViewListGetter(FlaskView):

    def __init__(self, model_cls, debug):
        self.model_cls = model_cls
        self.debug = debug

    def handler(self):
        with cosmos:
            query = None
            if self.model_cls.query_fields != None:
                query_schema = URLParams(self.model_cls.query_fields)
                query = query_schema.from_multi_dict(request.args)

            l = self.model_cls.get_list(**query)
            body = json.dumps(map(self.model_cls.to_json, l))
            return make_response(body, 200, {"Content-Type": "application/json"})


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
        url = "%s/%s/%s" % (self.model_cls.api.url, self.model_cls.__name__, id)
        res = requests.get(url)
        if res.status_code == 404:
            return None
        if res.status_code == 200:
            e = InternalServerError("Call returned an invalid value")
            e.remote = True
            if res.content == "":
                raise e
            try:
                return self.model_cls.from_json(json.loads(res.content))
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
