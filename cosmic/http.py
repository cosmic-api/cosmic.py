import json
import copy
import requests
from requests.structures import CaseInsensitiveDict

from werkzeug.exceptions import HTTPException, InternalServerError, abort
from werkzeug.routing import Rule
from werkzeug.routing import Map as RuleMap

from flask import Flask, make_response, current_app
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

    def get_flask_view(self, endpoint):

        def view(**url_args):
            from flask import request
            # Pull Request object out of Flask's magical local. From now
            # on, we'll pass it explicitly.
            try:
                return self.view(endpoint, request._get_current_object(), **url_args)
            except HTTPError as err:
                return error_response(err.message, err.code)
            except ValidationError as err:
                return error_response(str(err), 400)
            except Exception as exc:
                return self.unhandled_exception_hook(exc)

        return view

    def view(self, endpoint, request, **url_args):
        func_input = self.parse_request(endpoint, request, **url_args)
        func_output = endpoint.handler(**func_input)
        return self.build_response(endpoint, func_input=func_input, func_output=func_output)

    def unhandled_exception_hook(self, exc):
        if current_app.debug:
            raise
        else:
            return error_response("Internal Server Error", 500)

    def parse_request(self, endpoint, request, **url_args):
        return endpoint.parse_request(request, **url_args)

    def build_response(self, endpoint, func_input, func_output):
        return endpoint.build_response(func_input=func_input, func_output=func_output)




def error_response(message, code):
    body = json.dumps({"error": message})
    return make_response(body, code, {"Content-Type": "application/json"})


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

        if self.query_schema != None:
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

    def __init__(self, action, name):
        self.action = action
        self.url = "/actions/%s" % name

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
            required, optional = get_args(self.action.func)
            # If only one argument, take the whole object
            if len(required + optional) == 1:
                kwargs = {}
                kwargs[required[0]] = data
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
        if data == None:
            return make_response("", 204, {})
        else:
            body = json.dumps(data.datum)
            return make_response(body, 200, {"Content-Type": "application/json"})


class SpecEndpoint(Endpoint):
    """
    :Request:
        :Method: ``GET``
        :URL: ``/spec.json``

    :Response:
        :Code: ``200``
        :Body: The API spec as a JSON-encoded string.
        :ContentType: ``application/json``

    """
    method = "GET"
    never_authenticate = True
    json_response = True
    acceptable_response_codes = [200]

    def __init__(self, url, api):
        self.url = url
        self.api = api

    def handler(self):
        return self.api

    def parse_request(self, req, **url_args):
        return {}

    def build_request(self, *args, **kwargs):
        return super(SpecEndpoint, self).build_request()

    def parse_response(self, res):
        res = super(SpecEndpoint, self).parse_response(res)
        from .api import API
        return API.from_json(res['json'].datum)

    def build_response(self, func_input, func_output):
        from .api import API
        body = json.dumps(API.to_json(func_output))
        return make_response(body, 200, {"Content-Type": "application/json"})


class EnvelopeEndpoint(Endpoint):
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

    def parse_request(self, req, **url_args):
        req = super(EnvelopeEndpoint, self).parse_request(req, **url_args)
        return self.request_schema.from_json(req['json'].datum)

    def build_response(self, func_input, func_output):
        body = json.dumps(self.response_schema.to_json(func_output))
        return make_response(body, 200, {"Content-Type": "application/json"})



class GetByIdEndpoint(Endpoint):
    """
    :Request:
        :Method: ``GET``
        :URL: ``/<model>/<id>`` where *model* is the model name.
    :Response:
        :Code: ``200`` or ``404`` if object is not found.
        :Body: The object as a JSON-encoded string or empty if the object
            with the provided id does not exist.
        :ContentType: ``application/json`` if body is not empty.

    """
    method = "GET"
    json_response = True
    acceptable_response_codes = [404, 200]
    response_can_be_empty = True
    request_must_be_empty = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_get_%s" % self.model_cls.__name__

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
            return make_response("", 404, {})
        else:
            id = func_input['id']
            rep = func_output.value
            body = json.dumps(Representation(self.model_cls).to_json((id, rep)))
            return make_response(body, 200, {"Content-Type": "application/json"})

    def parse_response(self, res):
        res = super(GetByIdEndpoint, self).parse_response(res)
        if res['code'] == 404:
            raise NotFound
        if res['code'] == 200:
            (id, rep) = Representation(self.model_cls).from_json(res['json'].datum)
            return self.model_cls(id=id, **rep)


class UpdateEndpoint(Endpoint):
    """
    :Request:
        :Method: ``PUT``
        :URL: ``/<model>/<id>`` where *model* is the model name.
        :Body: New model representation as a JSON-encoded string.
        :ContentType: ``application/json``
    :Response:
        :Code: ``200``
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
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_put_%s" % self.model_cls.__name__

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
            return make_response("", 404, {})
        else:
            id = func_input['id']
            rep = func_output.value
            body = json.dumps(Representation(self.model_cls).to_json((id, rep)))
            return make_response(body, 200, {"Content-Type": "application/json"})

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
        :Body: New model representation as a JSON-encoded string.
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
        self.url = "/%s" % self.model_cls.__name__
        self.endpoint = "list_post_%s" % self.model_cls.__name__

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
        href = "/%s/%s" % (self.model_cls.__name__, func_output[0])
        return make_response(body, 201, {
            "Location": href,
            "Content-Type": "application/json"
        })


class DeleteEndpoint(Endpoint):
    """
    :Request:
        :Method: ``DELETE``
        :URL: ``/<model>/<id>`` where *model* is the model name.
    :Response:
        :Code: ``204``
        :Body: Empty.

    """
    method = "DELETE"
    acceptable_response_codes = [204, 404]
    response_must_be_empty = True
    request_must_be_empty = True

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.url = "/%s/<id>" % self.model_cls.__name__
        self.endpoint = "doc_delete_%s" % self.model_cls.__name__

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
            return make_response("", 404, {})
        else:
            return make_response("", 204, {})


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
                    }
                }

            In the above, *self* is the request URL, *model* is the name of
            the model that was requested and *repr* is a JSON representation
            of an instance of that model which was matched by the query.
            
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
        self.url = "/%s" % self.model_cls.__name__
        self.endpoint = "list_get_%s" % self.model_cls.__name__

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
        for jrep in j["_embedded"][self.model_cls._name]:
            l.append(Representation(self.model_cls).from_json(jrep))

        if self.model_cls.list_metadata:
            meta = j.copy()
            del meta['_embedded']
            del meta['_links']
            meta = Struct(self.model_cls.list_metadata).from_json(meta)
            return l, meta
        return l

    def build_response(self, func_input, func_output):
        self_link = "/%s" % self.model_cls.__name__
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

        body["_embedded"][self.model_cls._name] = []
        for inst in l:
            jrep = Representation(self.model_cls).to_json(inst)
            body["_embedded"][self.model_cls._name].append(jrep)

        return make_response(json.dumps(body), 200, {"Content-Type": "application/json"})


