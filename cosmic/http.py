import json

import requests
from werkzeug.exceptions import NotFound as WerkzeugNotFound
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Rule
from werkzeug.routing import Map as RuleMap

from .types import *
from .tools import get_args, string_to_json, args_to_datum, deserialize_json, \
    serialize_json
from .exceptions import *
from .globals import ensure_thread_local


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
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint_name, values = adapter.match()
        except WerkzeugNotFound:
            return error_response("Not Found", 404)

        if endpoint_name == 'spec':
            endpoint = SpecEndpoint(self.api.spec)

        elif endpoint_name == 'action':
            action_name = values.pop('action')
            if action_name not in self.api.spec['actions'].keys():
                return error_response("Not Found", 404)
            endpoint = ActionEndpoint(
                self.api.spec,
                action_name,
                getattr(self.api.actions, action_name))
        else:
            model_name = values.pop('model')
            if model_name not in self.api.spec['models'].keys():
                return error_response("Not Found", 404)
            model_spec = self.api.spec['models'][model_name]
            if not model_spec['methods'][endpoint_name]:
                return error_response("Method Not Allowed", 405)
            model_obj = getattr(self.api.models, model_name)
            endpoints = {
                'get_by_id': GetByIdEndpoint,
                'create': CreateEndpoint,
                'update': UpdateEndpoint,
                'delete': DeleteEndpoint,
                'get_list': GetListEndpoint,
            }
            args = {
                "api_spec": self.api.spec,
                "model_name": model_name,
                "func": getattr(model_obj, endpoint_name),
            }
            endpoint = endpoints[endpoint_name](**args)

        try:
            return self.view(endpoint, request, **values)
        except HTTPError as err:
            return error_response(err.message, err.code)

    def wsgi_app(self, environ, start_response):
        with ensure_thread_local():
            request = Request(environ)
            if self.debug:
                response = self.dispatch_request(request)
            else:
                try:
                    response = self.dispatch_request(request)
                except Exception as exc:
                    response = self.unhandled_exception_hook(exc, request)

            return response(environ, start_response)

    def unhandled_exception_hook(self, exc, request):
        return error_response("Internal Server Error", 500)

    def view(self, endpoint, request, **url_args):
        try:
            func_input = self.parse_request(endpoint, request, **url_args)
        except ValidationError as err:
            return error_response(str(err), 400)

        func_output = endpoint.handler(**func_input)
        return self.build_response(endpoint,
                                   func_input=func_input,
                                   func_output=func_output)

    def parse_request(self, endpoint, request, **url_args):
        return endpoint.parse_request(request, **url_args)

    def build_response(self, endpoint, func_input, func_output):
        return endpoint.build_response(func_input=func_input,
                                       func_output=func_output)





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
        return Box(json.loads(data))
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
    response_can_be_empty = True
    response_must_be_empty = None

    request_can_be_empty = True
    request_must_be_empty = None

    query_schema = None

    acceptable_exceptions = []

    def handler(self, *args, **kwargs):
        if not self.acceptable_exceptions:
            return self.func(*args, **kwargs)

        try:
            return Either(value=self.func(*args, **kwargs))
        except tuple(self.acceptable_exceptions) as e:
            return Either(exception=e)

    def parse_request(self, request, **url_args):
        req = {
            'url_args': url_args,
            'headers': request.headers
        }
        try:
            req['json'] = get_payload_from_http_message(request)
        except SpecError as e:
            raise HTTPError(code=400, message=e.args[0])

        is_empty = request.data == ""

        if ((self.request_must_be_empty == True and not is_empty) or
                (is_empty and self.request_can_be_empty == False)):
            raise HTTPError(code=400, message="Invalid data")

        if self.query_schema is not None:
            req['query'] = self.query_schema.from_multi_dict(request.args)

        return req

    def build_response(self, func_input, func_output):
        raise NotImplementedError()

    def build_request(self, data=None, url_args=None, headers=None, query=None):

        if url_args is None:
            url_args = {}
        if headers is None:
            headers = {}
        if query is None:
            query = {}

        if data is not None:
            headers["Content-Type"] = "application/json"
            string_data = json.dumps(data.datum)
        else:
            string_data = ""

        url = reverse_werkzeug_url(self.url, url_args)

        if self.query_schema is not None and query:
            query_string = self.query_schema.to_json(query)
            if query_string:
                url += "?%s" % query_string

        return requests.Request(
            method=self.method,
            url=url,
            data=string_data,
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

        try:
            r['json'] = string_to_json(res.text)
        except ValueError:
            raise SpecError("Unparseable response")

        if r['code'] not in self.acceptable_response_codes:
            message = None
            if 'json' in r and r['json'] and type(r['json'].datum) == dict and 'error' in r['json'].datum:
                message = r['json'].datum['error']

            raise RemoteHTTPError(code=r['code'], message=message)

        return r


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
    acceptable_response_codes = [200]

    def __init__(self, api_spec=None):
        self.url = '/spec.json'
        self.api_spec = api_spec

    def parse_request(self, req, **url_args):
        return {}

    def build_request(self, *args, **kwargs):
        return super(SpecEndpoint, self).build_request()

    def handler(self):
        return self.api_spec

    def parse_response(self, res):
        res = super(SpecEndpoint, self).parse_response(res)
        return APISpec.from_json(res['json'].datum)

    def build_response(self, func_input, func_output):
        body = json.dumps(APISpec.to_json(func_output))
        return Response(body, 200, {"Content-Type": "application/json"})


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
    acceptable_response_codes = [200, 204]

    def __init__(self, api_spec, action_name, func=None):
        self.func = func
        self.action_name = action_name
        self.action_spec = api_spec['actions'][action_name]
        self.accepts = self.action_spec.get('accepts', None)
        self.returns = self.action_spec.get('returns', None)
        self.url = "/actions/%s" % action_name

    def build_request(self, *args, **kwargs):
        packed = args_to_datum(*args, **kwargs)
        data = serialize_json(self.accepts, packed)
        return super(ActionEndpoint, self).build_request(data=data)

    def parse_request(self, req, **url_args):
        req = super(ActionEndpoint, self).parse_request(req, **url_args)
        data = deserialize_json(self.accepts, req['json'])
        kwargs = {}
        if data is not None:
            required_args, optional_args = get_args(self.func)
            # If only one argument, take the whole object
            if len(required_args + optional_args) == 1:
                kwargs = {required_args[0]: data}
            else:
                kwargs = data
        return kwargs

    def parse_response(self, res):
        res = super(ActionEndpoint, self).parse_response(res)
        if self.returns and res['json']:
            return self.returns.from_json(res['json'].datum)
        else:
            return None

    def build_response(self, func_input, func_output):
        data = serialize_json(self.returns, func_output)
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
    acceptable_response_codes = [404, 200]
    response_can_be_empty = True
    request_must_be_empty = True
    acceptable_exceptions = [NotFound]

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.url = "/%s/<id>" % model_name

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
            body = json.dumps(Representation(Model(self.full_model_name)).to_json((id, rep)))
            return Response(body, 200, {"Content-Type": "application/json"})

    def parse_response(self, res):
        res = super(GetByIdEndpoint, self).parse_response(res)
        if res['code'] == 404:
            raise NotFound
        if res['code'] == 200:
            (id, rep) = Representation(Model(self.full_model_name)).from_json(res['json'].datum)
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
    acceptable_response_codes = [200, 404]
    response_can_be_empty = False
    request_can_be_empty = False
    acceptable_exceptions = [NotFound]

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.url = "/%s/<id>" % model_name

    def build_request(self, id, **patch):
        return super(UpdateEndpoint, self).build_request(
            data=Box(Patch(Model(self.full_model_name)).to_json((id, patch))),
            url_args={'id': id})

    def parse_request(self, req, **url_args):
        req = super(UpdateEndpoint, self).parse_request(req, **url_args)
        id, rep = Patch(Model(self.full_model_name)).from_json(req['json'].datum)
        rep['id'] = req['url_args']['id']
        return rep

    def build_response(self, func_input, func_output):
        if func_output.exception is not None:
            return Response("", 404, {})
        else:
            id = func_input['id']
            rep = func_output.value
            body = json.dumps(Representation(Model(self.full_model_name)).to_json((id, rep)))
            return Response(body, 200, {"Content-Type": "application/json"})

    def parse_response(self, res):
        res = super(UpdateEndpoint, self).parse_response(res)
        if res['code'] == 200:
            return Representation(Model(self.full_model_name)).from_json(res['json'].datum)[1]
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
    acceptable_response_codes = [201]
    response_can_be_empty = False
    request_can_be_empty = False

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.url = "/%s" % model_name

    def build_request(self, **patch):
        return super(CreateEndpoint, self).build_request(
            data=Box(Patch(Model(self.full_model_name)).to_json((None, patch))))

    def parse_request(self, req, **url_args):
        req = super(CreateEndpoint, self).parse_request(req, **url_args)
        id, rep = Patch(Model(self.full_model_name)).from_json(req['json'].datum)
        return rep

    def parse_response(self, res):
        res = super(CreateEndpoint, self).parse_response(res)
        return Representation(Model(self.full_model_name)).from_json(res['json'].datum)

    def build_response(self, func_input, func_output):
        body = json.dumps(Representation(Model(self.full_model_name)).to_json(func_output))
        href = "/%s/%s" % (self.model_name, func_output[0])
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
    acceptable_exceptions = [NotFound]

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.url = "/%s/<id>" % model_name

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
    acceptable_response_codes = [200]
    response_can_be_empty = False
    request_must_be_empty = True

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.model_spec = api_spec['models'][model_name]
        self.list_metadata = self.model_spec['list_metadata']
        self.func = func
        self.query_schema = None
        if self.model_spec['query_fields']:
            self.query_schema = URLParams(self.model_spec['query_fields'])
        self.url = "/%s" % model_name

    def build_request(self, **query):
        return super(GetListEndpoint, self).build_request(query=query)

    def parse_request(self, req, **url_args):
        req = super(GetListEndpoint, self).parse_request(req, **url_args)
        return req.get('query', {})

    def parse_response(self, res):
        res = super(GetListEndpoint, self).parse_response(res)
        j = res['json'].datum
        l = []
        for jrep in j["_embedded"][self.model_name]:
            l.append(Representation(Model(self.full_model_name)).from_json(jrep))

        if self.list_metadata:
            meta = j.copy()
            del meta['_embedded']
            del meta['_links']
            meta = Struct(self.list_metadata).from_json(meta)
            return l, meta
        return l

    def build_response(self, func_input, func_output):
        self_link = "/%s" % self.model_name
        if self.query_schema and func_input:
            self_link += '?' + self.query_schema.to_json(func_input)

        body = {
            "_links": {
                "self": {"href": self_link}
            },
            "_embedded": {}
        }

        if self.list_metadata:
            l, meta = func_output
            meta = Struct(self.list_metadata).to_json(meta)
            body.update(meta)
        else:
            l = func_output

        body["_embedded"][self.model_name] = []
        for inst in l:
            jrep = Representation(Model(self.full_model_name)).to_json(inst)
            body["_embedded"][self.model_name].append(jrep)

        return Response(json.dumps(body), 200, {"Content-Type": "application/json"})


