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
    """This class represents the common interface for the server-side and the
    client-side API objects. It contains the API spec as well as a collection
    of functions for each API endpoint. On the server side, these functions
    are user-defined. On the client side, they are created automatically to
    execute HTTP calls.
    """

    def __init__(self, spec):
        #: The API spec, in its native form (see
        #: :class:`~cosmic.types.APISpec`)
        self.spec = spec
        #: This stores the action functions as properties of a plain object:
        #:
        #: .. code:: python
        #:
        #:     >>> spelling.actions.correct('simpl')
        #:     "simple"
        #:
        self.actions = Object()
        #: Through this property you can access the model functions
        #: :meth:`get_by_id`, :meth:`get_list`, :meth:`create`, :meth:`update`
        #: and :meth:`delete`. They are accessed as attributes:
        #:
        #: .. code:: python
        #:
        #:     >>> quotes.models.Quote.get_by_id("1")
        #:     {"text": "Know thyself.", "author": "Socrates"}
        #:
        self.models = Object()
        name = self.spec['name']
        if name in cosmos.keys():
            raise RuntimeError("API already exists: {}".format(name))
        cosmos[name] = self



class API(BaseAPI):
    """
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

    def run(self, port=5000, debug=False, **kwargs):
        """Simple way to run the API in development. The debug parameter gets
        passed into a :class:`~cosmic.http.Server` instance, all other
        parameters - into Werkzeug's :func:`~werkzeug.serving.run_simple`. For
        more serving options, see :ref:`guide-serving`.
        """
        from werkzeug.serving import run_simple
        from .http import Server

        server = Server(self, debug=debug)
        run_simple('127.0.0.1', port, server.wsgi_app, **kwargs)


    def action(self, accepts=None, returns=None):
        """A decorator for registering actions with API.

        The *accepts* parameter is a schema that describes the input of the
        function, *returns* is a schema that describes the output of the
        function. The name of the function becomes the name of the action and
        the docstring serves as the action's documentation.

        Once registered, an action will become accessible as an attribute of
        the :data:`~cosmic.api.BaseAPI.actions` object.

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
        model class is used as the name of the resulting model. A subclass
        of :class:`~cosmic.models.BaseModel` is used to supply the necessary
        metadata and functions to the API.

        .. code:: python

            >>> dictionary = API("dictionary")
            >>> @dictionary.model
            ... class Word(BaseModel):
            ...    properties = [
            ...        required("text", String)
            ...    ]
            ...

        Once registered, a model will become accessible as an attribute of the
        :data:`~cosmic.api.BaseAPI.models` object.
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

