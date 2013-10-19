from __future__ import unicode_literals

import json
import copy
import requests
from requests.structures import CaseInsensitiveDict

from werkzeug.exceptions import HTTPException, InternalServerError, NotFound, abort
from werkzeug.routing import Rule
from werkzeug.routing import Map as RuleMap

from flask import Flask, make_response, current_app, request
from .types import *

from teleport import ParametrizedWrapper, BasicWrapper
from collections import OrderedDict

from .tools import *
from .exceptions import *


class BaseClientHook(object):

    def call(self, endpoint, *args, **kwargs):
        req = self.build_request(endpoint, *args, **kwargs)
        res = self.make_request(endpoint, req)
        return self.parse_response(endpoint, res)

    def build_request(self, endpoint, *args, **kwargs):
        return endpoint.build_request(*args, **kwargs)

    def parse_response(self, endpoint, res):
        return endpoint.parse_response(res)


class ClientHook(BaseClientHook):

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.sessions.Session()

    def make_request(self, endpoint, request):
        request.url = self.base_url + request.url
        prepared = self.session.prepare_request(request)
        return self.session.send(prepared,
            stream=False,
            timeout=None,
            verify=True,
            cert=None,
            proxies={},
            allow_redirects=True)


class SaveStackClientHookMixin(object):

    def __init__(self, *args, **kwargs):
        self.stack = []
        self.__last_request = None
        super(SaveStackClientHookMixin, self).__init__(*args, **kwargs)

    def build_request(self, endpoint, *args, **kwargs):
        request = super(SaveStackClientHookMixin, self).build_request(endpoint, *args, **kwargs)
        self.__last_request = {
            "method": request.method,
            "data": request.data,
            "headers": copy.deepcopy(request.headers),
            "url": request.url,
        }
        return request

    def parse_response(self, endpoint, res):
        saved_resp = {
            "data": res.text,
            "headers": res.headers,
            "status_code": res.status_code
        }
        self.stack.append((self.__last_request, saved_resp))
        return super(SaveStackClientHookMixin, self).parse_response(endpoint, res)


class WerkzeugTestClientHook(BaseClientHook):

    def __init__(self, client):
        self.client = client

    def make_request(self, endpoint, request):
        kwargs = {
            "method": request.method,
            "data": request.data,
            "headers": request.headers
        }
        # Content-Type should be provided as kwarg because otherwise we can't
        # access request.mimetype
        if 'Content-Type' in request.headers:
            kwargs['content_type'] = request.headers.pop('Content-Type')
        r = self.client.open(path=request.url, **kwargs)
        resp = requests.Response()
        resp._content = r.data
        resp.headers = CaseInsensitiveDict(r.headers)
        resp.status_code = r.status_code

        return resp


class ServerHook(object):

    def view(self, endpoint, request, **url_args):
        try:
            parsed = self.parse_request(endpoint, request, **url_args)
            r = endpoint.handler(**parsed)
            return self.build_response(endpoint, r)
        except Exception as err:
            if current_app.debug:
                raise
            else:
                return error_to_response(err)

    def parse_request(self, endpoint, request, **url_args):
        return endpoint.parse_request(request, **url_args)

    def build_response(self, endpoint, *args, **kwargs):
        return endpoint.build_response(*args, **kwargs)




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

    never_authenticate = False

    response_can_be_empty = True
    response_must_be_empty = None

    request_can_be_empty = True
    request_must_be_empty = None

    query_schema = None

    def view(self, **url_args):
        return self.api.server_hook.view(self, request, **url_args)

    def parse_request(self, request, **url_args):
        req = {
            'url_args': url_args,
            'headers': request.headers
        }
        if self.json_request:
            req['json'] = get_payload_from_http_message(request)
        else:
            req['data'] = request.get_data()

        is_empty = request.get_data() == ""

        if ((self.request_must_be_empty == True and not is_empty) or
            (is_empty and self.request_can_be_empty == False)):
            raise SpecError()

        if self.query_schema != None:
            req['query'] = self.query_schema.from_multi_dict(request.args)

        return self._parse_request(req)

    def build_response(self, resp):
        return make_response(self._build_response(resp))

    def build_request(self, *args, **kwargs):
        r = self._build_request(*args, **kwargs)

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

        return requests.Request(
            method=self.method,
            url=url,
            data=data,
            headers=headers)

    def parse_response(self, res):
        e = InternalServerError("Call returned an invalid value")
        e.remote = True

        is_empty = res.text == ""
        if ((self.response_must_be_empty == True and not is_empty) or
                (is_empty and self.response_can_be_empty == False)):
            raise e

        r = {
            'code': res.status_code,
            'headers': res.headers
        }

        if self.json_response:
            try:
                r['json'] = string_to_json(res.text)
            except ValueError:
                raise e
        else:
            r['data'] = res.text

        if r['code'] not in self.acceptable_response_codes:
            message = None
            if 'json' in r and r['json'] and type(r['json'].datum) == dict and 'error' in r['json'].datum:
                message = r['json'].datum['error']
            try:
                abort(r['code'], message)
            except Exception as e:
                # Flag the exception to specify that it came from a remote
                # API. If this exception bubbles up to the web layer, a
                # generic 500 response will be returned
                e.remote = True
                raise

        try:
            return self._parse_response(r)
        except ValidationError as a:
            raise e

    def __call__(self, *args, **kwargs):
        return self.api.client_hook.call(self, *args, **kwargs)

    def get_url_rule(self):
        return {
            'rule': self.url,
            'view_func': self.view,
            'methods': [self.method],
            'endpoint': self.endpoint
        }


class FlaskViewAction(FlaskView):
    method = "POST"
    json_request = True
    json_response = True
    acceptable_response_codes = [200, 204]

    def __init__(self, function, url, api):
        self.function = function
        self.url = url
        self.api = api

    def handler(self, data):
        return self.function.json_to_json(data)

    def _build_request(self, *args, **kwargs):
        packed = pack_action_arguments(*args, **kwargs)
        return {"json": serialize_json(self.function.accepts, packed)}

    def _parse_request(self, req):
        return {'data': req['json']}

    def _parse_response(self, res):
        if self.function.returns and res['json']:
            return self.function.returns.from_json(res['json'].datum)
        else:
            return None

    def _build_response(self, data):
        if data == None:
            return ("", 204, {})
        else:
            body = json.dumps(data.datum)
            return (body, 200, {"Content-Type": "application/json"})


class Spec(FlaskView):
    method = "GET"
    never_authenticate = True
    json_response = True
    acceptable_response_codes = [200]

    def __init__(self, url, api):
        self.url = url
        self.api = api

    def handler(self):
        return self.api

    def _build_request(self, *args, **kwargs):
        return {}

    def _parse_request(self, req):
        return {}

    def _parse_response(self, res):
        from .api import API
        return API.from_json(res['json'].datum)

    def _build_response(self, api):
        from .api import API
        body = json.dumps(API.to_json(api))
        return (body, 200, {"Content-Type": "application/json"})


class Envelope(FlaskView):
    method = "POST"
    never_authenticate = True
    json_request = True
    json_response = True
    request_can_be_empty = False
    response_can_be_empty = False
    acceptable_response_codes = [200]

    request_schema = Struct([
        required("url", String),
        required("headers", Headers),
        required("method", String),
        required("body", String)
    ])
    response_schema = Struct([
        required("headers", Headers),
        required("code", Integer),
        required("body", String)
    ])

    def __init__(self, api):
        self.api = api
        self.url = '/envelope'
        self.endpoint = 'envelope'

    def handler(self, url, method, headers, body):
        content_type = headers.get("Content-Type", None)
        with current_app.test_request_context(url,
                method=method,
                headers=headers,
                content_type=content_type,
                data=body):
            response = current_app.full_dispatch_request()
        return {
            'code': response.status_code,
            'headers': response.headers,
            'body': response.data
        }

    def _parse_request(self, req):
        return self.request_schema.from_json(req['json'].datum)

    def _build_response(self, json_response):
        body = json.dumps(self.response_schema.to_json(json_response))
        return (body, 200, {"Content-Type": "application/json"})



class ModelGetter(FlaskView):
    method = "GET"
    json_response = True
    acceptable_response_codes = [404, 200]
    response_can_be_empty = True
    request_must_be_empty = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.api = model_cls.api
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_get_%s" % self.model_cls.__name__

    def handler(self, id):
        return self.model_cls.get_by_id(id)

    def _build_request(self, id):
        return {'url_args': {'id': id}}

    def _parse_request(self, req):
        return {'id': req['url_args']['id']}

    def _build_response(self, inst):
        if inst == None:
            return ("", 404, {})
        body = json.dumps(self.model_cls.to_json(inst))
        return (body, 200, {"Content-Type": "application/json"})

    def _parse_response(self, res):
        if res['code'] == 404:
            return None
        if res['code'] == 200:
            return self.model_cls.from_json(res['json'].datum)


class ModelPutter(FlaskView):
    method = "PUT"
    json_request = True
    json_response = True
    acceptable_response_codes = [200]
    response_can_be_empty = False
    request_can_be_empty = False

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.api = model_cls.api
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_put_%s" % self.model_cls.__name__

    def handler(self, id, inst):
        if self.model_cls.get_by_id(id) == None:
            raise NotFound
        assert inst.id == id
        inst.save()
        return inst

    def _build_request(self, id, inst):
        return {
            'json': Box(self.model_cls.to_json(inst)),
            'url_args': {'id': id}
        }

    def _parse_request(self, req):
        return {
            'id': req['url_args']['id'],
            'inst': self.model_cls.from_json(req['json'].datum)
        }

    def _build_response(self, inst):
        body = json.dumps(self.model_cls.to_json(inst))
        return (body, 200, {"Content-Type": "application/json"})

    def _parse_response(self, res):
        return self.model_cls.from_json(res['json'].datum)



class ListPoster(FlaskView):
    method = "POST"
    json_request = True
    json_response = True
    acceptable_response_codes = [201]
    response_can_be_empty = False
    request_can_be_empty = False

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.api = model_cls.api
        self.url = "/%s" % self.model_cls.__name__
        self.endpoint = "list_post_%s" % self.model_cls.__name__

    def handler(self, inst):
        inst.save()
        return inst

    def _build_request(self, inst):
        return {'json': Box(self.model_cls.to_json(inst))}

    def _parse_request(self, req):
        return {'inst': self.model_cls.from_json(req['json'].datum)}

    def _parse_response(self, res):
        return self.model_cls.from_json(res['json'].datum)

    def _build_response(self, inst):
        body = json.dumps(self.model_cls.to_json(inst))
        return (body, 201, {
            "Location": inst.href,
            "Content-Type": "application/json"
        })


class ModelDeleter(FlaskView):
    method = "DELETE"
    acceptable_response_codes = [204]
    response_must_be_empty = True
    request_must_be_empty = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.api = model_cls.api
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_delete_%s" % self.model_cls.__name__

    def handler(self, inst):
        if inst == None:
            raise NotFound
        inst.delete()

    def _build_request(self, inst):
        return {'url_args': {'id': inst.id}}

    def _parse_request(self, req):
        return {'inst': self.model_cls.get_by_id(req['url_args']['id'])}

    def _parse_response(self, res):
        return

    def _build_response(self, _):
        return ("", 204, {})


class ListGetter(FlaskView):
    method = "GET"
    json_response = True
    acceptable_response_codes = [200]
    response_can_be_empty = False
    request_must_be_empty = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.api = model_cls.api
        if self.model_cls.query_fields != None:
            self.query_schema = URLParams(self.model_cls.query_fields)
        self.url = "/%s" % self.model_cls.__name__
        self.endpoint = "list_get_%s" % self.model_cls.__name__

    def handler(self, **query):
        self_link = self.url

        if self.query_schema != None and query:
            self_link += "?" + self.query_schema.to_json(query)

        return (self.model_cls.get_list(**query), self_link)

    def _build_request(self, **query):
        return {"query": query}

    def _parse_request(self, req):
        return req.get('query', {})

    def _parse_response(self, res):
        j = res['json'].datum
        return map(self.model_cls.from_json, j["_embedded"][self.model_cls.__name__])

    def _build_response(self, tup):
        l, self_link = tup
        body = {
            "_links": {
                "self": {"href": self_link}
            },
            "_embedded": {}
        }
        body["_embedded"][self.model_cls.__name__] = map(self.model_cls.to_json, l)
        return (json.dumps(body), 200, {"Content-Type": "application/json"})


