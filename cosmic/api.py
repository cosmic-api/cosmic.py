from __future__ import unicode_literals
import json
import inspect
from collections import OrderedDict

from .tools import get_args, assert_is_compatible, \
    validate_underscore_identifier
from .types import *
from .globals import cosmos
from . import MODEL_METHODS


class Object(object):
    pass


class BaseAPI(object):

    def __init__(self, spec):
        self.spec = spec
        self.models = Object()
        self.actions = Object()
        cosmos[self.spec['name']] = self



class API(BaseAPI):
    """An instance of this class represents a Cosmic API, whether it's your
    own API being served or a third-party API being consumed. In the former
    case, the API object is instantiated by the constructor and is bound to a
    database ORM and other user-defined functions. In the latter case, it is
    instantiated by the :meth:`API.load` method and these functions are
    replaced by automatically generated HTTP calls.

    One of the primary goals of Cosmic is to make local and remote APIs behave
    as similarly as possible.

    :param name: The API name is required, and should be unique
    :param homepage: If you like, the API spec may include a link to your
        homepage
    """

    def __init__(self, name, homepage=None):
        super(API, self).__init__({
            "name": name,
            "homepage": homepage,
            "actions": OrderedDict(),
            "models": OrderedDict(),
        })

    def run(self, port=5000, **kwargs):
        """Simple way to run the API in development. Uses Werkzeug's
        :meth:`werkzeug.serving.run_simple` internally. See
        :ref:`guide-serving` for more options.
        """
        from werkzeug.serving import run_simple
        from .http import Server

        server = Server(self)
        run_simple('127.0.0.1', port, server.wsgi_app, **kwargs)


    def action(self, accepts=None, returns=None):
        """A decorator for creating actions out of functions and registering
        them with the API.

        The *accepts* parameter is a schema that describes the input of the
        function, *returns* is a schema that describes the output of the
        function. The name of the function becomes the name of the action and
        the docstring serves as the action's documentation.

        Once registered, an action will become accessible as an attribute of
        the :data:`~cosmic.api.API.actions` object.

        .. code:: python

            >>> random = API("random")
            >>> @random.action(returns=Integer)
            ... def generate():
            ...     "Random enough"
            ...     return 9
            >>> random.actions.generate()
            9

        """

        def wrapper(func):
            name = unicode(func.__name__)
            validate_underscore_identifier(name)
            required_args, optional_args = get_args(func)

            if accepts:
                assert_is_compatible(accepts, required_args, optional_args)

            doc = inspect.getdoc(func)
            self.spec['actions'][name] = {
                "accepts": accepts,
                "returns": returns,
                "doc": doc,
            }

            setattr(self.actions, name, func)

            return func

        return wrapper

    def model(self, model_cls):
        """A decorator for registering a model with an API. The name of the
        model class is used as the name of the resulting model.

        .. code:: python

            >>> dictionary = API("dictionary")
            >>> @dictionary.model
            ... class Word(BaseModel):
            ...    properties = [
            ...        required("text", String)
            ...    ]
            ...

        Once registered, a model will become accessible as an attribute of the
        :data:`~cosmic.api.API.models` object.
        """

        name = model_cls.__name__

        m = Object()
        m.validate_patch = model_cls.validate_patch

        methods = {}
        for method in MODEL_METHODS:
            methods[method] = method in model_cls.methods
            setattr(m, method, getattr(model_cls, method))

        self.spec['models'][unicode(name)] = {
            "properties": OrderedDict(model_cls.properties),
            "links": OrderedDict(model_cls.links),
            "query_fields": OrderedDict(model_cls.query_fields),
            "list_metadata": OrderedDict(model_cls.list_metadata),
            "methods": methods,
        }
        APISpec.assemble(self.spec)
        setattr(self.models, name, m)

        return model_cls

