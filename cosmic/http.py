import json

import requests
from werkzeug.exceptions import NotFound as WerkzeugNotFound
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Rule
from werkzeug.routing import Map as RuleMap
from werkzeug.http import parse_options_header

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


class PipeCannotBeEmpty(object):

    def forward(self, text_data, **kwargs):
        if text_data == '':
            raise HTTPError(code=400, message="Invalid data")

    backward = forward


class PipeMustBeEmpty(object):

    def forward(self, text_data, **kwargs):
        if text_data != '':
            raise HTTPError(code=400, message="Invalid data")

    backward = forward


class PipeJSONPayload(object):

    def forward(self, text_data, headers, **kwargs):
        if text_data == "":
            return {"json_data": None}
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
            return {"json_data": Box(json.loads(data))}
        except ValueError:
            raise HTTPError(400, "Invalid JSON")

    def backward(self, json_data, headers, **kwargs):
        _headers = {"Content-Type": "application/json"}
        _headers.update(headers)
        if json_data is not None:
            text_data = json.dumps(json_data.datum)
        else:
            text_data = ""
        return {
            "text_data": text_data,
            "headers": _headers
        }


class PipeQueryParse(object):

    def __init__(self, schema):
        self.schema = schema

    def forward(self, query_string, **kwargs):
        return {"query": self.schema.from_json(query_string)}

    def backward(self, query, **kwargs):
        return {"query_string": self.schema.to_json(query)}


class PipeURL(object):

    def __init__(self, url_template):
        self.url_template = url_template
        rule = Rule(url_template, endpoint='_')
        self.c = RuleMap([rule]).bind('example.com')

    def forward(self, path, **kwargs):
        url_args = self.c.match(path)[1]
        return {"url_args": url_args}

    def backward(self, url_args, **kwargs):
        url = self.c.build('_', url_args)
        return {"path": url}


class PipeResponseCodes(object):

    def __init__(self, *acceptable_codes):
        self.acceptable_codes = acceptable_codes

    def forward(self, code, text_data, headers, **kwargs):
        if code not in self.acceptable_codes:
            message = None
            try:
                json_data = PipeJSONPayload().forward(
                    text_data=text_data,
                    headers=headers)['json_data']
                message = json_data.datum['error']
            except Exception:
                pass
            raise RemoteHTTPError(code=code, message=message)

    def backward(self, **kwargs):
        pass


def error_response(message, code):
    body = json.dumps({"error": message})
    return Response(body, code, {"Content-Type": "application/json"})



class Endpoint(object):

    acceptable_exceptions = []

    request_pipeline = []
    response_pipeline = []

    def handler(self, *args, **kwargs):
        if not self.acceptable_exceptions:
            return self.func(*args, **kwargs)

        try:
            return Either(value=self.func(*args, **kwargs))
        except tuple(self.acceptable_exceptions) as e:
            return Either(exception=e)

    def parse_request(self, request):

        args = {
            'text_data': request.data,
            'query_string': request.query_string,
            'headers': request.headers,
            'path': request.path
        }

        for step in self.request_pipeline:
            more = step.forward(**args)
            if more is not None:
                args.update(more)

        return self._parse_request(**args)

    def build_response(self, func_input, func_output):
        res = self._build_response(func_input, func_output)

        args = {
            'json_data': res.get('json_data', None),
            'headers': res.get('headers', {}),
            'code': res['code']
        }

        for step in reversed(self.response_pipeline):
            more = step.backward(**args)
            if more is not None:
                args.update(more)

        body = args['text_data']
        code = args['code']
        headers = args.get('headers', {})
        return Response(body, code, headers)

    def build_request(self, *args, **kwargs):

        req = self._build_request(*args, **kwargs)

        args = {
            'json_data': req.get('data', None),
            'headers': req.get('headers', {}),
            'query': req.get('query', {}),
            'url_args': req.get('url_args', {})
        }

        for step in reversed(self.request_pipeline):
            more = step.backward(**args)
            if more is not None:
                args.update(more)

        url = args['path']
        if 'query_string' in args and args['query_string']:
            url += "?%s" % args['query_string']

        return requests.Request(
            method=self.method,
            url=url,
            data=args['text_data'],
            headers=args['headers'])

    def parse_response(self, res):

        args = {
            'code': res.status_code,
            'text_data': res.text,
            'headers': res.headers
        }

        for step in self.response_pipeline:
            more = step.forward(**args)
            if more is not None:
                args.update(more)

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
    method = "GET"

    request_pipeline = [
        PipeURL('/spec.json'),
        PipeJSONPayload()
    ]

    response_pipeline = [
        PipeResponseCodes(200),
        PipeJSONPayload()
    ]

    def __init__(self, api_spec=None):
        self.api_spec = api_spec

    def _parse_request(self, **kwargs):
        return {}

    def _build_request(self, **kwargs):
        return {}

    def handler(self):
        return self.api_spec

    def _parse_response(self, json_data, **kwargs):
        return APISpec.from_json(json_data.datum)

    def _build_response(self, func_input, func_output):
        return {'code': 200, 'json_data': Box(APISpec.to_json(func_output))}


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

    def __init__(self, api_spec, action_name, func=None):
        self.func = func
        self.action_name = action_name
        self.action_spec = api_spec['actions'][action_name]
        self.accepts = self.action_spec.get('accepts', None)
        self.returns = self.action_spec.get('returns', None)
        self.request_pipeline = [
            PipeURL("/actions/%s" % action_name),
            PipeJSONPayload()
        ]
        self.response_pipeline = [
            PipeResponseCodes(200, 204),
            PipeJSONPayload()
        ]

    def _build_request(self, *args, **kwargs):
        packed = args_to_datum(*args, **kwargs)
        return {"data": serialize_json(self.accepts, packed)}

    def _parse_request(self, json_data, **kwargs):
        data = deserialize_json(self.accepts, json_data)
        kwargs = {}
        if data is not None:
            required_args, optional_args = get_args(self.func)
            # If only one argument, take the whole object
            if len(required_args + optional_args) == 1:
                kwargs = {required_args[0]: data}
            else:
                kwargs = data
        return kwargs

    def _parse_response(self, json_data, **kwargs):
        if self.returns and json_data:
            return self.returns.from_json(json_data.datum)
        else:
            return None

    def _build_response(self, func_input, func_output):
        data = serialize_json(self.returns, func_output)
        if data is None:
            code = 204
        else:
            code = 200
        return {'code': code, 'json_data': data}


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
    acceptable_exceptions = [NotFound]

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.request_pipeline = [
            PipeURL("/%s/<id>" % model_name),
            PipeMustBeEmpty(),
            PipeJSONPayload()
        ]
        self.response_pipeline = [
            PipeResponseCodes(200, 404),
            PipeJSONPayload()
        ]


    def _build_request(self, id):
        return {"url_args": {'id': id}}

    def _parse_request(self, url_args, **kwargs):
        return {'id': url_args['id']}

    def _build_response(self, func_input, func_output):
        if func_output.exception is not None:
            return {'code': 404}
        else:
            id = func_input['id']
            rep = func_output.value
            data = Box(Representation(Model(self.full_model_name)).to_json((id, rep)))
            return {'code': 200, 'json_data': data}

    def _parse_response(self, code, json_data, **kwargs):
        if code == 404:
            raise NotFound
        if code == 200:
            _, rep = Representation(Model(self.full_model_name)).from_json(json_data.datum)
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
    acceptable_exceptions = [NotFound]

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.request_pipeline = [
            PipeURL("/%s/<id>" % model_name),
            PipeCannotBeEmpty(),
            PipeJSONPayload()
        ]
        self.response_pipeline = [
            PipeResponseCodes(200, 404),
            PipeCannotBeEmpty(),
            PipeJSONPayload()
        ]


    def _build_request(self, id, **patch):
        return {
            "data": Box(Patch(Model(self.full_model_name)).to_json((id, patch))),
            "url_args": {'id': id}
        }

    def _parse_request(self, json_data, url_args, **kwargs):
        id, rep = Patch(Model(self.full_model_name)).from_json(json_data.datum)
        rep['id'] = url_args['id']
        return rep

    def _build_response(self, func_input, func_output):
        if func_output.exception is not None:
            return {'code': 404}
        else:
            id = func_input['id']
            rep = func_output.value
            data = Box(Representation(Model(self.full_model_name)).to_json((id, rep)))
            return {'code': 200, 'json_data': data}

    def _parse_response(self, code, json_data, **kwargs):
        if code == 200:
            return Representation(Model(self.full_model_name)).from_json(json_data.datum)[1]
        if code == 404:
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

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.request_pipeline = [
            PipeURL("/%s" % model_name),
            PipeJSONPayload()
        ]
        self.response_pipeline = [
            PipeResponseCodes(201),
            PipeCannotBeEmpty(),
            PipeJSONPayload()
        ]


    def _build_request(self, **patch):
        return {
            "data": Box(Patch(Model(self.full_model_name)).to_json((None, patch)))
        }

    def _parse_request(self, json_data, **kwargs):
        id, rep = Patch(Model(self.full_model_name)).from_json(json_data.datum)
        return rep

    def _parse_response(self, json_data, **kwargs):
        return Representation(Model(self.full_model_name)).from_json(json_data.datum)

    def _build_response(self, func_input, func_output):
        data = Box(Representation(Model(self.full_model_name)).to_json(func_output))
        href = "/%s/%s" % (self.model_name, func_output[0])
        return {
            'code': 201,
            'json_data': data,
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
    method = "DELETE"
    acceptable_exceptions = [NotFound]

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.func = func
        self.request_pipeline = [
            PipeURL("/%s/<id>" % model_name),
            PipeMustBeEmpty(),
            PipeJSONPayload()
        ]
        self.response_pipeline = [
            PipeResponseCodes(204, 404),
            PipeMustBeEmpty(),
            PipeJSONPayload()
        ]

    def _build_request(self, id):
        return {"url_args": {'id': id}}

    def _parse_request(self, url_args, **kwargs):
        return {'id': url_args['id']}

    def _parse_response(self, code, **kwargs):
        if code == 204:
            return None
        if code == 404:
            raise NotFound

    def _build_response(self, func_input, func_output):
        if func_output.exception is not None:
            return {'code': 404}
        else:
            return {'code': 204}


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
    method = "GET"

    def __init__(self, api_spec, model_name, func=None):
        self.model_name = model_name
        self.full_model_name = "{}.{}".format(api_spec['name'], model_name)
        self.model_spec = api_spec['models'][model_name]
        self.list_metadata = self.model_spec['list_metadata']
        self.func = func
        self.request_pipeline = [
            PipeURL("/%s" % model_name),
            PipeMustBeEmpty(),
            PipeJSONPayload()
        ]
        self.response_pipeline = [
            PipeResponseCodes(200),
            PipeCannotBeEmpty(),
            PipeJSONPayload()
        ]
        if self.model_spec['query_fields']:
            query_schema = URLParams(self.model_spec['query_fields'])
            self.request_pipeline += [PipeQueryParse(query_schema)]

    def _build_request(self, **query):
        return {"query": query}

    def _parse_request(self, query, **kwargs):
        return query

    def _parse_response(self, json_data, **kwargs):
        j = json_data.datum
        l = []
        for jrep in j["_embedded"][self.model_name]:
            l.append(Representation(Model(self.full_model_name)).from_json(jrep))

        if self.list_metadata:
            meta = j.copy()
            del meta['_embedded']
            meta = Struct(self.list_metadata).from_json(meta)
            return l, meta
        return l

    def _build_response(self, func_input, func_output):
        body = {
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

        return {
            'code': 200,
            'json_data': Box(body)
        }


