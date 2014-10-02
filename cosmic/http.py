import json
import sys

import requests
from werkzeug.exceptions import NotFound as WerkzeugNotFound
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Rule
from werkzeug.routing import Map as RuleMap
from werkzeug.http import parse_options_header

from .types import *
from .tools import get_args, args_to_datum
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
            return self.view(endpoint, request)
        except HTTPError as err:
            return error_response(err.message, err.code)
        except ValidationError as err:
            return error_response(str(err), 400)

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

    def view(self, endpoint, request):
        func_input = self.parse_request(endpoint, request)
        func_output = endpoint.handler(**func_input)
        return self.build_response(endpoint,
                                   func_input=func_input,
                                   func_output=func_output)

    def parse_request(self, endpoint, request):
        return endpoint.parse_request(request)

    def build_response(self, endpoint, func_input, func_output):
        return endpoint.build_response(func_input=func_input,
                                       func_output=func_output)


def update(d, **kwargs):
    d = d.copy()
    d.update(kwargs)
    return d


class PipeJSONPayload(object):

    def forward(self, text_data, headers, **kwargs):
        if text_data == '':
            raise HTTPError(code=400, message="Invalid data")
        mimetype, params = parse_options_header(headers['Content-Type'])
        if mimetype != "application/json":
            raise HTTPError(400, 'Content-Type must be "application/json" got "%s" instead' % mimetype)
        charset = params.get("charset", "utf-8")
        if charset.lower() != "utf-8":
            raise HTTPError(400, 'Content-Type charset must be "utf-8" got %s instead' % charset)
        try:
            data = text_data.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPError(400, "Unicode Decode Error")
        try:
            return update(kwargs,
                          json_data=json.loads(data),
                          headers=headers)
        except ValueError:
            raise HTTPError(400, "Invalid JSON")

    def backward(self, json_data, headers=None, **kwargs):
        _headers = {"Content-Type": "application/json"}
        if headers: _headers.update(headers)
        text_data = json.dumps(json_data)
        return update(kwargs,
                      text_data=text_data,
                      headers=_headers)


class PipeQueryParse(object):

    def __init__(self, query_fields):
        self.schema = URLParams(query_fields)

    def forward(self, query_string, **kwargs):
        return update(kwargs, query=self.schema.from_json(query_string))

    def backward(self, query, **kwargs):
        return update(kwargs, query_string=self.schema.to_json(query))


class PipeMethod(object):

    def __init__(self, method):
        self.method = method

    def forward(self, **kwargs):
        return kwargs

    def backward(self, **kwargs):
        return update(kwargs, method=self.method)


class PipeStaticURL(object):

    def __init__(self, url):
        self.url = url

    def forward(self, **kwargs):
        return kwargs

    def backward(self, **kwargs):
        return update(kwargs, path=self.url)


class PipeURL(object):

    def __init__(self, url_template):
        self.url_template = url_template
        rule = Rule(url_template, endpoint='_')
        self.c = RuleMap([rule]).bind('example.com')

    def forward(self, path, **kwargs):
        url_args = self.c.match(path)[1]
        return update(kwargs, url_args=url_args)

    def backward(self, url_args, **kwargs):
        path = self.c.build('_', url_args)
        return update(kwargs, path=path)


class PipeResponseCode(object):

    def __init__(self, code):
        self.code = code

    def forward(self, code, text_data, headers, **kwargs):
        if code == self.code:
            return update(kwargs, text_data=text_data, code=code, headers=headers)
        message = None
        try:
            json_data = PipeJSONPayload().forward(
                text_data=text_data,
                headers=headers)['json_data']
            message = json_data['error']
        except Exception:
            pass
        raise RemoteHTTPError(code=code, message=message)

    def backward(self, **kwargs):
        return update(kwargs, code=self.code)


class PipeBodySchema(object):

    def __init__(self, schema):
        self.schema = schema

    def forward(self, json_data, **kwargs):
        return update(kwargs, data=self.schema.from_json(json_data))

    def backward(self, data, **kwargs):
        return update(kwargs, json_data=self.schema.to_json(data))


def error_response(message, code):
    body = json.dumps({"error": message})
    return Response(body, code, {"Content-Type": "application/json"})



class Endpoint(object):

    exceptions = {}

    request_pipeline = []
    response_pipeline = []

    def handler(self, *args, **kwargs):
        try:
            return Either(value=self.func(*args, **kwargs))
        except tuple(self.exceptions.values()) as e:
            return Either(exception=sys.exc_info())

    def parse_request(self, request):

        args = {
            'text_data': request.data,
            'query_string': request.query_string,
            'headers': request.headers,
            'path': request.path,
            'method': request.method
        }

        for step in self.request_pipeline:
            args = step.forward(**args)

        return self._parse_request(**args)

    def build_response(self, func_input, func_output):
        if func_output.exception:
            for code, exc_class in self.exceptions.items():
                if func_output.exception[0] == exc_class:
                    return Response('', code, {})

        args = self._build_response(func_input, func_output.value)

        for step in reversed(self.response_pipeline):
            args = step.backward(**args)

        code = args['code']
        body = args.get('text_data', '')
        headers = args.get('headers', {})
        return Response(body, code, headers)

    def build_request(self, *args, **kwargs):

        args = self._build_request(*args, **kwargs)

        for step in reversed(self.request_pipeline):
            args = step.backward(**args)

        url = args['path']
        if 'query_string' in args and args['query_string']:
            url += "?%s" % args['query_string']

        return requests.Request(
            method=args['method'],
            url=url,
            data=args.get('text_data', ''),
            headers=args.get('headers', {}))

    def parse_response(self, res):

        if res.status_code in self.exceptions.keys():
            raise self.exceptions[res.status_code]()

        args = {
            'code': res.status_code,
            'text_data': res.text,
            'headers': res.headers
        }

        for step in self.response_pipeline:
            args = step.forward(**args)

        return self._parse_response(**args)


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

    request_pipeline = [
        PipeStaticURL('/spec.json'),
        PipeMethod('GET')
    ]

    response_pipeline = [
        PipeResponseCode(200),
        PipeJSONPayload(),
        PipeBodySchema(APISpec)
    ]

    def __init__(self, api_spec=None):
        self.func = lambda: api_spec

    def _parse_request(self, **kwargs):
        return {}

    def _build_request(self, **kwargs):
        return {}

    def _parse_response(self, data, **kwargs):
        return data

    def _build_response(self, func_input, func_output):
        return {'data': func_output}


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


    def __init__(self, api_spec, action_name, func=None):
        self.func = func
        action_spec = api_spec['actions'][action_name]
        self.request_pipeline = [
            PipeStaticURL("/actions/%s" % action_name),
            PipeMethod('POST'),
        ]
        if 'accepts' in action_spec:
            self.request_pipeline += [
                PipeJSONPayload(),
                PipeBodySchema(action_spec['accepts'])
            ]
        else:
            self._parse_request = lambda **kwargs: {}
            self._build_request = lambda *args, **kwargs: {}
        if 'returns' in action_spec:
            self.response_pipeline = [
                PipeResponseCode(200),
                PipeJSONPayload(),
                PipeBodySchema(action_spec['returns'])
            ]
            self._parse_response = lambda data, **kwargs: data
            self._build_response = lambda func_input, func_output: {'data': func_output}
        else:
            self.response_pipeline = [
                PipeResponseCode(204)
            ]
            self._build_response = lambda *args: {}
            self._parse_response = lambda **kwargs: None

    def _build_request(self, *args, **kwargs):
        return {"data": args_to_datum(*args, **kwargs)}

    def _parse_request(self, data, **kwargs):
        required_args, optional_args = get_args(self.func)
        # If only one argument, take the whole object
        if len(required_args + optional_args) == 1:
            return {required_args[0]: data}
        else:
            return data


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
    exceptions = {404: NotFound}

    def __init__(self, api_spec, model_name, func=None):
        full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.request_pipeline = [
            PipeURL("/%s/<id>" % model_name),
            PipeMethod('GET')
        ]
        self.response_pipeline = [
            PipeResponseCode(200),
            PipeJSONPayload(),
            PipeBodySchema(Representation(Model(full_model_name)))
        ]

    def _build_request(self, id):
        return {"url_args": {'id': id}}

    def _parse_request(self, url_args, **kwargs):
        return {'id': url_args['id']}

    def _build_response(self, func_input, func_output):
        id = func_input['id']
        rep = func_output
        return {'data': (id, rep)}

    def _parse_response(self, data, **kwargs):
        _, rep = data
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
    exceptions = {404: NotFound}

    def __init__(self, api_spec, model_name, func=None):
        full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.request_pipeline = [
            PipeURL("/%s/<id>" % model_name),
            PipeMethod('PUT'),
            PipeJSONPayload(),
            PipeBodySchema(Patch(Model(full_model_name)))
        ]
        self.response_pipeline = [
            PipeResponseCode(200),
            PipeJSONPayload(),
            PipeBodySchema(Representation(Model(full_model_name)))
        ]

    def _build_request(self, id, patch):
        return {
            "data": (id, patch),
            "url_args": {'id': id}
        }

    def _parse_request(self, data, url_args, **kwargs):
        id, rep = data
        return {
            'id': url_args['id'],
            'patch': rep
        }

    def _build_response(self, func_input, func_output):
        id = func_input['id']
        rep = func_output
        return {'data': (id, rep)}

    def _parse_response(self, data, **kwargs):
        _, rep = data
        return rep


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

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.request_pipeline = [
            PipeStaticURL("/%s" % model_name),
            PipeMethod('POST'),
            PipeJSONPayload(),
            PipeBodySchema(
                Patch(Model(full_model_name)))
        ]
        self.response_pipeline = [
            PipeResponseCode(201),
            PipeJSONPayload(),
            PipeBodySchema(
                Representation(Model(full_model_name)))
        ]


    def _build_request(self, patch):
        return {"data": (None, patch)}

    def _parse_request(self, data, **kwargs):
        _, rep = data
        return {'patch': rep}

    def _parse_response(self, data, **kwargs):
        return data

    def _build_response(self, func_input, func_output):
        href = "/%s/%s" % (self.model_name, func_output[0])
        return {
            'data': func_output,
            'headers': {"Location": href}
        }


class DeleteEndpoint(Endpoint):
    """
    :Request:
        :Method: ``DELETE``
        :URL: ``/<model>/<id>`` where *model* is the model name.
    :Response:
        :Code: ``204`` or ``404`` if object is not found.
        :Body: Empty.

    """
    exceptions = {404: NotFound}

    def __init__(self, api_spec, model_name, func=None):
        model_name = model_name
        self.func = func
        self.request_pipeline = [
            PipeURL("/%s/<id>" % model_name),
            PipeMethod('DELETE')
        ]
        self.response_pipeline = [
            PipeResponseCode(204)
        ]

    def _build_request(self, id):
        return {"url_args": {'id': id}}

    def _parse_request(self, url_args, **kwargs):
        return {'id': url_args['id']}

    def _parse_response(self, **kwargs):
        return None

    def _build_response(self, func_input, func_output):
        return {}


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
                    "_embedded": {
                        <model>: [<repr>*]
                    },
                    <metadata>*
                }

            *Metadata* is defined according to
            :data:`~cosmic.models.BaseModel.list_metadata`.

    """

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        full_model_name = "{}.{}".format(api_spec['name'], model_name)
        model_spec = api_spec['models'][model_name]
        self.list_metadata = model_spec['list_metadata']
        self.func = func
        query_fields = model_spec.get('query_fields', [])

        schema = Struct([
            required('_embedded', Struct([
                required(self.model_name,
                         Array(Representation(Model(full_model_name))))
            ]))
        ] + self.list_metadata.items())

        self.request_pipeline = [
            PipeStaticURL("/%s" % model_name),
            PipeMethod('GET'),
            PipeQueryParse(query_fields)
        ]
        self.response_pipeline = [
            PipeResponseCode(200),
            PipeJSONPayload(),
            PipeBodySchema(schema)
        ]

    def _build_request(self, **query):
        return {"query": query}

    def _parse_request(self, query, **kwargs):
        return query

    def _parse_response(self, data, **kwargs):
        reps = data['_embedded'][self.model_name]

        if self.list_metadata:
            meta = data.copy()
            del meta['_embedded']
            return reps, meta
        return reps

    def _build_response(self, func_input, func_output):
        data = {"_embedded": {}}

        if self.list_metadata:
            reps, meta = func_output
            data.update(meta)
        else:
            reps = func_output

        data["_embedded"][self.model_name] = reps

        return {'data': data}


