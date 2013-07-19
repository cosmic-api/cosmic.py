from __future__ import unicode_literals

import json
import requests
from requests.structures import CaseInsensitiveDict

from werkzeug.exceptions import HTTPException, InternalServerError, NotFound, abort
from werkzeug.urls import url_decode, url_encode
from werkzeug.datastructures import MultiDict
from werkzeug.routing import Rule
from werkzeug.routing import Map as RuleMap

from flask import Flask, make_response, current_app
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
        # Content-Type header seems to be ignored, content_type as kwarg
        # works. Possibly a bug in Flask/Werkzeug.
        if 'headers' in kwargs and 'Content-Type' in kwargs['headers']:
            kwargs['content_type'] = kwargs['headers'].pop('Content-Type')
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

def error_to_response(err):
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

def response_to_error(res):
    message = None
    if res.json and 'error' in res.json:
        message = res.json['error']
    # Flag the exception to specify that it came from a remote
    # API. If this exception bubbles up to the web layer, a
    # generic 500 response will be returned
    try:
        abort(res.status_code, message)
    except Exception as e:
        e.remote = True
        return e

def get_payload_from_http_message(req):
    bytes = req.get_data()
    if not bytes:
        return None
    if req.mimetype != "application/json":
        raise SpecError('Content-Type must be "application/json" got "%s" instead' % req.mimetype)
    charset = req.mimetype_params.get("charset", "utf-8")
    if charset.lower() != "utf-8":
        raise SpecError('Content-Type charset must be "utf-8" got %s instead' % charset)
    try:
        data = bytes.decode('utf-8')
    except UnicodeDecodeError as e:
        raise SpecError("Unicode Decode Error")
    try:
        return string_to_json(data)
    except ValueError:
        raise SpecError("Invalid JSON")

def reverse_werkzeug_url(url, values):
    rule = Rule(url)
    # Rule needs to be bound before building
    m = RuleMap([rule])
    # Note: this seems to be changing in Werkzeug master
    domain_part, url = rule.build(values)
    return url



class FlaskView(object):
    json_request = False
    json_response = False
    query_schema = None

    def view(self, **url_args):
        try:
            req = {
                'url_args': url_args,
                'headers': request.headers
            }
            if self.json_request:
                req['json'] = get_payload_from_http_message(request)
            else:
                req['data'] = request.get_data()

            if self.query_schema != None:
                req['query'] = self.query_schema.from_multi_dict(request.args)

            # Make sure the current TypeMap is on the Teleport context stack
            with cosmos:
                if hasattr(self, "parse_request"):
                    return make_response(self.handler(**self.parse_request(req)))
                else:
                    return make_response(self.handler(req))
        except Exception as err:
            if current_app.debug:
                raise
            else:
                return error_to_response(err)

    def __call__(self, *args, **kwargs):
        r = self.build_request(*args, **kwargs)

        if self.json_request:
            data = json_to_string(r.get('json', None))
        else:
            data = r.get('data', "")

        url_args = r.get('url_args', {})
        headers = r.get('headers', {})
        query = r.get('query', {})
        url = reverse_werkzeug_url(self.url, url_args)

        if self.json_request and data:
            headers["Content-Type"] = "application/json"

        if self.query_schema != None and query:
            query_string = self.query_schema.to_json(query)
            if query_string:
                url += "?%s" % query_string

        if hasattr(self, "_request"):
            req_func = self._request
        else:
            req_func = self.model_cls.api._request

        res = req_func(
            url=url,
            method=self.method,
            data=data,
            headers=headers)

        r = {
            'code': res.status_code,
            'headers': res.headers
        }

        if self.json_response:
            try:
                r['json'] = string_to_json(res.text)
            except ValueError:
                e = InternalServerError("Call returned an invalid value")
                e.remote = True
                raise e
        else:
            r['data'] = res.text

        return self.parse_response(r)

    def add_to_blueprint(self, blueprint):
        blueprint.add_url_rule(self.url,
            view_func=self.view,
            methods=[self.method],
            endpoint=self.endpoint)


class FlaskViewAction(FlaskView):
    method = "POST"
    json_request = True
    json_response = True

    def __init__(self, function, url, api):
        self.function = function
        self.url = url
        if hasattr(api, '_request'):
            self._request = api._request

    def handler(self, req):
        data = self.function.json_to_json(req['json'])
        if data == None:
            return ("", 204, {})
        else:
            body = json.dumps(data.datum)
            return (body, 200, {"Content-Type": "application/json"})

    def build_request(self, *args, **kwargs):
        packed = pack_action_arguments(*args, **kwargs)
        return {
            "json": serialize_json(self.function.accepts, packed)
        }

    def parse_response(self, res):
        if res['code'] != requests.codes.ok:
            message = None
            if res['json'] and 'error' in res['json'].datum:
                message = res['json'].datum['error']
            try:
                abort(res['code'], message)
            except Exception as e:
                # Flag the exception to specify that it came from a remote
                # API. If this exception bubbles up to the web layer, a
                # generic 500 response will be returned
                e.remote = True
                raise
        try:
            if self.function.returns and res['json']:
                return self.function.returns.from_json(res['json'].datum)
            else:
                return None
        except ValidationError:
            e = InternalServerError("Call returned an invalid value")
            e.remote = True
            raise e




class ModelGetter(FlaskView):
    method = "GET"
    json_response = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_get_%s" % self.model_cls.__name__

    def handler(self, id):
        model = self.model_cls.get_by_id(id)
        if model == None:
            raise NotFound
        body = json.dumps(self.model_cls.to_json(model))
        return (body, 200, {"Content-Type": "application/json"})

    def build_request(self, id):
        return {'url_args': {'id': id}}

    def parse_request(self, req):
        return {'id': req['url_args']['id']}

    def parse_response(self, res):
        if res['code'] == 404:
            return None
        if res['code'] == 200:
            e = InternalServerError("Call returned an invalid value")
            e.remote = True
            if not res['json']:
                raise e
            try:
                return self.model_cls.schema.from_json(res['json'].datum)
            except ValidationError:
                raise e
            except ValueError:
                raise e
        else:
            message = None
            if res['json'] and 'error' in res['json']:
                message = res.json['error']
            try:
                abort(res['code'], message)
            except Exception as e:
                # Flag the exception to specify that it came from a remote
                # API. If this exception bubbles up to the web layer, a
                # generic 500 response will be returned
                e.remote = True
                raise




class ModelPutter(FlaskView):
    method = "PUT"
    json_request = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_put_%s" % self.model_cls.__name__

    def handler(self, id, inst):
        if self.model_cls.get_by_id(id) == None:
            raise NotFound
        assert inst.id == id
        inst.save()
        return ("", 204, {})

    def build_request(self, id, inst):
        return {
            'json': Box(self.model_cls.to_json(inst)),
            'url_args': {'id': id}
        }

    def parse_request(self, req):
        return {
            'id': req['url_args']['id'],
            'inst': self.model_cls.from_json(req['json'].datum)
        }

    def parse_response(self, res):
        if res['code'] == 204:
            return
        else:
            raise response_to_error(res)



class ListPoster(FlaskView):
    method = "POST"
    json_request = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s" % self.model_cls.__name__
        self.endpoint = "list_post_%s" % self.model_cls.__name__

    def handler(self, inst):
        inst.save()
        return ("", 201, {
            "Location": inst.href
        })

    def build_request(self, inst):
        return {'json': Box(self.model_cls.to_json(inst))}

    def parse_request(self, req):
        return {'inst': self.model_cls.from_json(req['json'].datum)}

    def parse_response(self, res):
        if res['code'] == 201:
            return self.model_cls.id_from_url(res['headers']["Location"])
        else:
            raise response_to_error(res)



class ModelDeleter(FlaskView):
    method = "DELETE"

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_delete_%s" % self.model_cls.__name__

    def handler(self, inst):
        if inst == None:
            raise NotFound
        inst.delete()
        return ("", 204, {})

    def build_request(self, inst):
        return {'url_args': {'id': inst.id}}

    def parse_request(self, req):
        return {'inst': self.model_cls.get_by_id(req['url_args']['id'])}

    def parse_response(self, res):
        if res['code'] == 204:
            return
        else:
            raise response_to_error(res)



class ListGetter(FlaskView):
    method = "GET"
    json_response = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        if self.model_cls.query_fields != None:
            self.query_schema = URLParams(self.model_cls.query_fields)
        self.url = "/%s" % self.model_cls.__name__
        self.endpoint = "list_get_%s" % self.model_cls.__name__

    def handler(self, **query):
        self_link = self.url

        if self.query_schema != None and query:
            self_link += "?" + self.query_schema.to_json(query)

        l = self.model_cls.get_list(**query)
        body = {
            "_links": {
                "self": {"href": self_link}
            },
            "_embedded": {}
        }
        body["_embedded"][self.model_cls.__name__] = map(self.model_cls.to_json, l)
        return (json.dumps(body), 200, {"Content-Type": "application/json"})

    def build_request(self, **query):
        return {"query": query}

    def parse_request(self, req):
        return req.get('query', {})

    def parse_response(self, res):
        if res['code'] == 200:
            e = InternalServerError("Call returned an invalid value")
            e.remote = True
            if not res['json']:
                raise e
            try:
                j = res['json'].datum
                return map(self.model_cls.from_json, j["_embedded"][self.model_cls.__name__])
            except (ValidationError, ValueError, KeyError):
                raise e
        else:
            raise response_to_error(res)

