import json
import copy

import requests
from requests.sessions import Session
from requests.structures import CaseInsensitiveDict

from werkzeug.test import Client as WerkzeugTestClient
from werkzeug.wrappers import Response

from .api import BaseAPI, Object
from .types import *
from .globals import cosmos
from .http import CreateEndpoint, DeleteEndpoint, GetByIdEndpoint, \
    GetListEndpoint, UpdateEndpoint, ActionEndpoint, SpecEndpoint


class BaseAPIClient(BaseAPI):

    def __init__(self, *args, **kwargs):
        super(BaseAPIClient, self).__init__(*args, **kwargs)
        self._generate_handler_objects()

    def call(self, endpoint, *args, **kwargs):
        req = self.build_request(endpoint, *args, **kwargs)
        res = self.make_request(endpoint, req)
        return self.parse_response(endpoint, res)

    def build_request(self, endpoint, *args, **kwargs):
        return endpoint.build_request(*args, **kwargs)

    def parse_response(self, endpoint, res):
        return endpoint.parse_response(res)

    def make_request(self, endpoint, request):
        raise NotImplementedError()

    def _generate_handler_objects(self):
        from functools import partial

        spec = self.spec

        for name, action in spec["actions"].items():
            setattr(self.actions, name,
                    partial(self.call, ActionEndpoint(spec, name)))

        for name, modeldef in spec["models"].items():
            m = Object()
            m.create = partial(self.call, CreateEndpoint(spec, name))
            m.update = partial(self.call, UpdateEndpoint(spec, name))
            m.delete = partial(self.call, DeleteEndpoint(spec, name))
            m.get_list = partial(self.call, GetListEndpoint(spec, name))
            m.get_by_id = partial(self.call, GetByIdEndpoint(spec, name))
            m.validate_patch = lambda patch: None

            setattr(self.models, name, m)


class APIClient(BaseAPIClient):
    verify = True
    base_url = None

    def __init__(self, *args, **kwargs):
        self.session = Session()
        spec = self.call(SpecEndpoint())
        super(APIClient, self).__init__(*args, spec=spec, **kwargs)

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


class WsgiAPIClient(BaseAPIClient):
    wsgi_app = None
    server_cosmos = None

    def __init__(self, *args, **kwargs):
        self.client = WerkzeugTestClient(self.wsgi_app, response_wrapper=Response)
        spec = self.call(SpecEndpoint())
        super(WsgiAPIClient, self).__init__(*args, spec=spec, **kwargs)

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

        if self.server_cosmos is None:
            r = self.client.open(path=request.url, **kwargs)
        else:
            with cosmos.scope(self.server_cosmos):
                r = self.client.open(path=request.url, **kwargs)


        resp = requests.Response()
        resp._content = r.data
        resp.headers = CaseInsensitiveDict(r.headers)
        resp.status_code = r.status_code

        return resp


class ClientLoggingMixin(object):

    def __init__(self, *args, **kwargs):
        self.log = []
        self.__last_request = None
        super(ClientLoggingMixin, self).__init__(*args, **kwargs)

    def build_request(self, endpoint, *args, **kwargs):
        request = super(ClientLoggingMixin, self).build_request(endpoint, *args, **kwargs)
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
        return super(ClientLoggingMixin, self).parse_response(endpoint, res)



