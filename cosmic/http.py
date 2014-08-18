import copy
import json

import requests
from requests.structures import CaseInsensitiveDict
from werkzeug.exceptions import NotFound as WerkzeugNotFound
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Rule
from werkzeug.routing import Map as RuleMap
from werkzeug.test import Client as WerkzeugTestClient

from .types import *
from .tools import get_args, string_to_json, args_to_datum, deserialize_json, serialize_json, json_to_string
from .exceptions import *


class Server(object):
    url_map = RuleMap([
        Rule('/spec.json', endpoint='spec', methods=['GET']),
        Rule('/actions/<action>', endpoint='action', methods=['POST']),
        Rule('/<model>/<id>', endpoint='get_by_id', methods=['GET']),
        Rule('/<model>/<id>', endpoint='update', methods=['PUT']),
        Rule('/<model>/<id>', endpoint='delete', methods=['DELETE']),
        Rule('/<model>', endpoint='create', methods=['POST']),
        Rule('/<model>', endpoint='get_list', methods=['GET']),
    ])

    def __init__(self, api, debug=False):
        self.api = api
        self.debug = debug

    def dispatch_request(self, request):
        from .api import API

        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint_name, values = adapter.match()
        except WerkzeugNotFound:
            return error_response("Not Found", 404)

        if endpoint_name == 'spec':
            body = json.dumps(API.to_json(self.api))
            return Response(body, 200, {"Content-Type": "application/json"})

        if endpoint_name == 'action':
            action_name = values.pop('action')
            if action_name not in self.api._actions:
                return error_response("Not Found", 404)
            action = self.api._actions[action_name]
            endpoint = ActionEndpoint(action)
        else:
            model_name = values.pop('model')
            if model_name not in self.api._models:
                return error_response("Not Found", 404)
            model_cls = self.api._models[model_name]
            if endpoint_name not in model_cls.methods:
                return error_response("Method Not Allowed", 405)
            endpoints = {
                'get_by_id': GetByIdEndpoint,
                'update': UpdateEndpoint,
                'delete': DeleteEndpoint,
                'create': CreateEndpoint,
                'get_list': GetListEndpoint,
            }
            endpoint = endpoints[endpoint_name](model_cls)

        try:
            return self.view(endpoint, request, **values)
        except HTTPError as err:
            return error_response(err.message, err.code)
        except ValidationError as err:
            return error_response(str(err), 400)
        except Exception as exc:
            return self.unhandled_exception_hook(exc)

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def unhandled_exception_hook(self, exc):
        if self.debug:
            raise
        else:
            return error_response("Internal Server Error", 500)

    def view(self, endpoint, request, **url_args):
        func_input = self.parse_request(endpoint, request, **url_args)
        func_output = endpoint.handler(**func_input)
        return self.build_response(endpoint, func_input=func_input, func_output=func_output)

    def parse_request(self, endpoint, request, **url_args):
        return endpoint.parse_request(request, **url_args)

    def build_response(self, endpoint, func_input, func_output):
        return endpoint.build_response(func_input=func_input, func_output=func_output)


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
    def __init__(self, base_url=None, verify=True):
        self.base_url = base_url
        self.verify = verify
        self.session = requests.sessions.Session()

    def make_request(self, endpoint, request):
        request.url = self.base_url + request.url
        prepared = self.session.prepare_request(request)
        return self.session.send(prepared,
                                 stream=False,
                                 timeout=None,
                                 verify=self.verify,
                                 cert=None,
                                 proxies={},
                                 allow_redirects=True)


class ClientHookLoggingMixin(BaseClientHook):
    def __init__(self, *args, **kwargs):
        self.log = []
        self.__last_request = None
        super(ClientHookLoggingMixin, self).__init__(*args, **kwargs)

    def build_request(self, endpoint, *args, **kwargs):
        request = super(ClientHookLoggingMixin, self).build_request(endpoint, *args, **kwargs)
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
        self.log.append((self.__last_request, saved_resp))
        return super(ClientHookLoggingMixin, self).parse_response(endpoint, res)


class WsgiClientHook(BaseClientHook):
    def __init__(self, wsgi_app):
        self.client = WerkzeugTestClient(wsgi_app, response_wrapper=Response)

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


def error_response(message, code):
    body = json.dumps({"error": message})
    return Response(body, code, {"Content-Type": "application/json"})


def get_payload_from_http_message(req):
    bytes = req.data
    if not bytes:
        return None
    if req.mimetype != "application/json":
        raise SpecError('Content-Type must be "application/json" got "%s" instead' % req.mimetype)
    charset = req.mimetype_params.get("charset", "utf-8")
    if charset.lower() != "utf-8":
        raise SpecError('Content-Type charset must be "utf-8" got %s instead' % charset)
    try:
        data = bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise SpecError("Unicode Decode Error")
    try:
        return string_to_json(data)
    except ValueError:
        raise SpecError("Invalid JSON")


def reverse_werkzeug_url(url, values):
    rule = Rule(url)
    # Rule needs to be bound before building
    RuleMap([rule])
    # Note: this seems to be changing in Werkzeug master
    domain_part, url = rule.build(values)
    return url


class Endpoint(object):
    json_request = False
    json_response = False

    never_authenticate = False

    response_can_be_empty = True
    response_must_be_empty = None

    request_can_be_empty = True
    request_must_be_empty = None

    query_schema = None

    def parse_request(self, request, **url_args):
        req = {
            'url_args': url_args,
            'headers': request.headers
        }
        if self.json_request:
            try:
                req['json'] = get_payload_from_http_message(request)
            except SpecError as e:
                raise HTTPError(code=400, message=e.args[0])
        else:
            req['data'] = request.data

        is_empty = request.data == ""

        if ((self.request_must_be_empty == True and not is_empty) or
                (is_empty and self.request_can_be_empty == False)):
            raise HTTPError(code=400, message="Invalid data")

        if self.query_schema is not None:
            req['query'] = self.query_schema.from_multi_dict(request.args)

        return req

    def build_response(self, func_input, func_output):
        raise NotImplementedError()

    def build_request(self,
                      json=None,
                      data="",
                      url_args={},
                      headers={},
                      query={}):

        if self.json_request:
            data = json_to_string(json)

        url = reverse_werkzeug_url(self.url, url_args)

        if self.json_request and data:
            headers["Content-Type"] = "application/json"

        if self.query_schema is not None and query:
            query_string = self.query_schema.to_json(query)
            if query_string:
                url += "?%s" % query_string

        return requests.Request(
            method=self.method,
            url=url,
            data=data,
            headers=headers)

    def parse_response(self, res):

        is_empty = res.text == ""
        if ((self.response_must_be_empty == True and not is_empty) or
                (is_empty and self.response_can_be_empty == False)):
            raise SpecError("Invalid response")

        r = {
            'code': res.status_code,
            'headers': res.headers
        }

        if self.json_response:
            try:
                r['json'] = string_to_json(res.text)
            except ValueError:
                raise SpecError("Unparseable response")
        else:
            r['data'] = res.text

        if r['code'] not in self.acceptable_response_codes:
            message = None
            if 'json' in r and r['json'] and type(r['json'].datum) == dict and 'error' in r['json'].datum:
                message = r['json'].datum['error']

            raise RemoteHTTPError(code=r['code'], message=message)

        return r


class ActionEndpoint(Endpoint):
    """
    :Request:
        :Method: ``POST``
        :URL: ``/actions/<action>`` where *action* is the action name.
        :Body: The action parameters as a JSON-encoded string or empty if the
            action expects no parameters.
        :ContentType: ``application/json`` if body is not empty.
    :Response:
        :Code: ``200`` or ``204`` if body is empty.
        :Body: The return value as a JSON-encoded string or empty if the actions
            has no return value.
        :ContentType: ``application/json`` if body is not empty.

    """

    method = "POST"
    json_request = True
    json_response = True
    acceptable_response_codes = [200, 204]

    def __init__(self, action):
        self.action = action
        self.url = "/actions/%s" % action.name

    def handler(self, *args, **kwargs):
        return self.action.func(*args, **kwargs)

    def build_request(self, *args, **kwargs):
        packed = args_to_datum(*args, **kwargs)
        json = serialize_json(self.action.accepts, packed)
        return super(ActionEndpoint, self).build_request(json=json)

    def parse_request(self, req, **url_args):
        req = super(ActionEndpoint, self).parse_request(req, **url_args)
        data = deserialize_json(self.action.accepts, req['json'])
        kwargs = {}
        if data is not None:
            required_args, optional_args = get_args(self.action.func)
            # If only one argument, take the whole object
            if len(required_args + optional_args) == 1:
                kwargs = {required_args[0]: data}
            else:
                kwargs = data
        return kwargs

    def parse_response(self, res):
        res = super(ActionEndpoint, self).parse_response(res)
        if self.action.returns and res['json']:
            return self.action.returns.from_json(res['json'].datum)
        else:
            return None

    def build_response(self, func_input, func_output):
        data = serialize_json(self.action.returns, func_output)
        if data is None:
            return Response("", 204, {})
        else:
            body = json.dumps(data.datum)
            return Response(body, 200, {"Content-Type": "application/json"})


class GetByIdEndpoint(Endpoint):
    """
    :Request:
        :Method: ``GET``
        :URL: ``/<model>/<id>`` where *model* is the model name.
    :Response:
        :Code: ``200`` or ``404`` if object is not found.
        :Body: The object representation as a JSON-encoded string.
        :ContentType: ``application/json`` if body is not empty.

    """
    method = "GET"
    json_response = True
    acceptable_response_codes = [404, 200]
    response_can_be_empty = True
    request_must_be_empty = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s/<id>" % self.model_cls.name
        self.endpoint = "doc_get_%s" % self.model_cls.name

    def handler(self, id):
        try:
            return Either(value=self.model_cls.get_by_id(id))
        except NotFound as e:
            return Either(exception=e)

    def build_request(self, id):
        return super(GetByIdEndpoint, self).build_request(
            url_args={'id': id})

    def parse_request(self, req, **url_args):
        req = super(GetByIdEndpoint, self).parse_request(req, **url_args)
        return {'id': req['url_args']['id']}

    def build_response(self, func_input, func_output):
        if func_output.exception is not None:
            return Response("", 404, {})
        else:
            id = func_input['id']
            rep = func_output.value
            body = json.dumps(Representation(self.model_cls).to_json((id, rep)))
            return Response(body, 200, {"Content-Type": "application/json"})

    def parse_response(self, res):
        res = super(GetByIdEndpoint, self).parse_response(res)
        if res['code'] == 404:
            raise NotFound
        if res['code'] == 200:
            (id, rep) = Representation(self.model_cls).from_json(res['json'].datum)
            return rep


class UpdateEndpoint(Endpoint):
    """
    :Request:
        :Method: ``PUT``
        :URL: ``/<model>/<id>`` where *model* is the model name.
        :Body: A corresponding model patch as a JSON-encoded string.
        :ContentType: ``application/json``
    :Response:
        :Code: ``200`` or ``404`` if object is not found.
        :Body: New model representation as a JSON-encoded string.
        :ContentType: ``application/json``

    """
    method = "PUT"
    json_request = True
    json_response = True
    acceptable_response_codes = [200, 404]
    response_can_be_empty = False
    request_can_be_empty = False

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s/<id>" % self.model_cls.name
        self.endpoint = "doc_put_%s" % self.model_cls.name

    def handler(self, id, **patch):
        self.model_cls.validate_patch(patch)
        try:
            return Either(value=self.model_cls.update(id, **patch))
        except NotFound as e:
            return Either(exception=e)

    def build_request(self, id, **patch):
        return super(UpdateEndpoint, self).build_request(
            json=Box(Patch(self.model_cls).to_json((id, patch))),
            url_args={'id': id})

    def parse_request(self, req, **url_args):
        req = super(UpdateEndpoint, self).parse_request(req, **url_args)
        id, rep = Patch(self.model_cls).from_json(req['json'].datum)
        rep['id'] = req['url_args']['id']
        return rep

    def build_response(self, func_input, func_output):
        if func_output.exception is not None:
            return Response("", 404, {})
        else:
            id = func_input['id']
            rep = func_output.value
            body = json.dumps(Representation(self.model_cls).to_json((id, rep)))
            return Response(body, 200, {"Content-Type": "application/json"})

    def parse_response(self, res):
        res = super(UpdateEndpoint, self).parse_response(res)
        if res['code'] == 200:
            return Representation(self.model_cls).from_json(res['json'].datum)[1]
        if res['code'] == 404:
            raise NotFound


class CreateEndpoint(Endpoint):
    """
    :Request:
        :Method: ``POST``
        :URL: ``/<model>`` where *model* is the model name.
        :Body: Corresponding model patch as a JSON-encoded string.
        :ContentType: ``application/json``
    :Response:
        :Code: ``201``
        :Body: New model representation as a JSON-encoded string.
        :ContentType: ``application/json``

    """
    method = "POST"
    json_request = True
    json_response = True
    acceptable_response_codes = [201]
    response_can_be_empty = False
    request_can_be_empty = False

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s" % self.model_cls.name
        self.endpoint = "list_post_%s" % self.model_cls.name

    def handler(self, **patch):
        self.model_cls.validate_patch(patch)
        return self.model_cls.create(**patch)

    def build_request(self, **patch):
        return super(CreateEndpoint, self).build_request(
            json=Box(Patch(self.model_cls).to_json((None, patch))))

    def parse_request(self, req, **url_args):
        req = super(CreateEndpoint, self).parse_request(req, **url_args)
        id, rep = Patch(self.model_cls).from_json(req['json'].datum)
        return rep

    def parse_response(self, res):
        res = super(CreateEndpoint, self).parse_response(res)
        return Representation(self.model_cls).from_json(res['json'].datum)

    def build_response(self, func_input, func_output):
        body = json.dumps(Representation(self.model_cls).to_json(func_output))
        href = "/%s/%s" % (self.model_cls.name, func_output[0])
        return Response(body, 201, {
            "Location": href,
            "Content-Type": "application/json"
        })


class DeleteEndpoint(Endpoint):
    """
    :Request:
        :Method: ``DELETE``
        :URL: ``/<model>/<id>`` where *model* is the model name.
    :Response:
        :Code: ``204`` or ``404`` if object is not found.
        :Body: Empty.

    """
    method = "DELETE"
    acceptable_response_codes = [204, 404]
    response_must_be_empty = True
    request_must_be_empty = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s/<id>" % self.model_cls.name
        self.endpoint = "doc_delete_%s" % self.model_cls.name

    def handler(self, id):
        try:
            return Either(value=self.model_cls.delete(id))
        except NotFound as e:
            return Either(exception=e)

    def build_request(self, id):
        return super(DeleteEndpoint, self).build_request(
            url_args={'id': id})

    def parse_request(self, req, **url_args):
        req = super(DeleteEndpoint, self).parse_request(req, **url_args)
        return {'id': req['url_args']['id']}

    def parse_response(self, res):
        res = super(DeleteEndpoint, self).parse_response(res)
        if res['code'] == 204:
            return None
        if res['code'] == 404:
            raise NotFound

    def build_response(self, func_input, func_output):
        if func_output.exception is not None:
            return Response("", 404, {})
        else:
            return Response("", 204, {})


class GetListEndpoint(Endpoint):
    """
    :Request:
        :Method: ``GET``
        :URL: ``/<model>`` where *model* is the model name.
        :Query: Query parameters serialized by the model's *query_schema*
    :Response:
        :Code: ``200``
        :ContentType: ``application/json``
        :Body:

            The syntax follows `JSON HAL
            <http://stateless.co/hal_specification.html>`_ specification.

            .. code::

                {
                    "_links": {
                        "self": {"href": <self>}
                    },
                    "_embedded": {
                        <model>: [<repr>*]
                    },
                    <metadata>*
                }

            In the above, *self* is the request URL, *model* is the name of
            the model that was requested and *repr* is a JSON-encoded
            representation of an object matched by the query. *Metadata* is
            defined according to
            :data:`~cosmic.models.BaseModel.list_metadata`.

    """
    method = "GET"
    json_response = True
    acceptable_response_codes = [200]
    response_can_be_empty = False
    request_must_be_empty = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.query_schema = None
        if self.model_cls.query_fields is not None:
            self.query_schema = URLParams(self.model_cls.query_fields)
        self.url = "/%s" % self.model_cls.name
        self.endpoint = "list_get_%s" % self.model_cls.name

    def handler(self, **query):
        return self.model_cls.get_list(**query)

    def build_request(self, **query):
        return super(GetListEndpoint, self).build_request(query=query)

    def parse_request(self, req, **url_args):
        req = super(GetListEndpoint, self).parse_request(req, **url_args)
        return req.get('query', {})

    def parse_response(self, res):
        res = super(GetListEndpoint, self).parse_response(res)
        j = res['json'].datum
        l = []
        for jrep in j["_embedded"][self.model_cls.name]:
            l.append(Representation(self.model_cls).from_json(jrep))

        if self.model_cls.list_metadata:
            meta = j.copy()
            del meta['_embedded']
            del meta['_links']
            meta = Struct(self.model_cls.list_metadata).from_json(meta)
            return l, meta
        return l

    def build_response(self, func_input, func_output):
        self_link = "/%s" % self.model_cls.name
        if self.query_schema and func_input:
            self_link += '?' + self.query_schema.to_json(func_input)

        body = {
            "_links": {
                "self": {"href": self_link}
            },
            "_embedded": {}
        }

        if self.model_cls.list_metadata:
            l, meta = func_output
            meta = Struct(self.model_cls.list_metadata).to_json(meta)
            body.update(meta)
        else:
            l = func_output

        body["_embedded"][self.model_cls.name] = []
        for inst in l:
            jrep = Representation(self.model_cls).to_json(inst)
            body["_embedded"][self.model_cls.name].append(jrep)

        return Response(json.dumps(body), 200, {"Content-Type": "application/json"})


