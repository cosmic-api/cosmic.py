Guide
=====

Installation
------------

Assuming you are running Linux or OS X and are familiar with
`pip <http://www.pip-installer.org/en/latest/quickstart.html>`_, installation
is as easy as:

.. code:: bash

   $ pip install cosmic

If you would like to work on the bleeding edge of Cosmic development, you
can clone the repo using git:

.. code:: bash
    
    $ git clone https://github.com/cosmic-api/cosmic.py.git cosmic-py

Then to install the current version (ideally you want to do this in a
virtualenv):

.. code:: bash

    $ cd cosmic-py
    $ python setup.py develop

If you are not yet familiar with `virtualenv
<http://www.virtualenv.org/en/latest/>`_, it is an indespensible tool for
Python development. It lets you create isolated Python environments for every
project you are working on. This means that different projects can depend on
different versions of the same library.

What's in an API?
-----------------

A web API is:

* An interface through which a server can share data and functionality with
  clients over the internet.
* A component of the server architecture that glues the database and business
  logic to HTTP.

In the context of Cosmic, an API is represented, unsurprisingly, by an
instance of the :class:`~cosmic.api.BaseAPI` class. On the server, we use
the :class:`~cosmic.api.API` subclass, and on the client we use the
:class:`~cosmic.client.APIClient` subclass.

The API object on the server and the API object are almost identical. The
difference is that for every server endpoint, there is a hook into the
server's database or business logic, whereas each client endpoint replaces
this with an HTTP call.

The client get created automatically from a JSON spec. The format of this
spec is defined by the Teleport type :class:`~cosmic.types.APISpec`. Let's see
what the spec looks like:

.. code:: python

    >>> from cosmic.types import APISpec
    >>> from cosmic.api import API
    >>> trivia = API("trivia", homepage="http://example.com")
    >>> APISpec.to_json(trivia.spec)
    {
        u'name': 'trivia',
        u'homepage': 'http://example.com',
        u'actions': {u'map': {}, u'order': []},
        u'models': {u'map': {}, u'order': []}
    }

Let's take a look at what's inside.

First, there is the basic metadata: the API *name* and *homepage*. The name of
the API should be unique. Though this is not yet enforced by Cosmic, we plan on
indexing Cosmic APIs on our website in which case it will become a requirement.

Then, the API spec contains descriptions of *actions* and *models*. These will
be explained in detail in the next two sections.

Auto-generated Clients
----------------------

In Cosmic, creating an API client is very easy. If you run the API from the
:doc:`tutorial <tutorial>`, you can create a client in another file simply by subclassing
:class:`~cosmic.client.APIClient` like so:

.. code:: python

    from cosmic.client import APIClient

    class WordsClient(APIClient):
        base_url = 'http://127.0.0.1:5000'

    words = WordsClient()
    print words.actions.pluralize('pencil')

You can use this subclass to override some HTTP functions necessary for
authentication, for example, to add an ``Authorization`` header to every
request.

.. _guide-actions:

RPC via Actions
---------------

.. seealso::

    :class:`~cosmic.http.ActionEndpoint` for HTTP spec.

RPC stands for remote procedure call. It allows remote clients to call
procedures (functions) in your code. These are commonly implemented as POST
handlers on action-style URLs, such as ``POST /register_user``. Cosmic goes
along with this convention, listening to POST requests on ``/actions/<name>``
URLs.

So what's in an action? Clearly, we need a name in order to generate the URL.
But apart from the name, Cosmic also expects type definitions for the input
and output values of the action. These definitions are used for serialization,
validation and help with generating documentation. Here is the Teleport schema
that describes an action:

.. code:: python

    Struct([
        optional("accepts", Schema),
        optional("returns", Schema),
        optional("doc", String)
    ])

Actions are registered with the :meth:`~cosmic.API.action` decorator:

.. code:: python

    >>> from cosmic.types import Array, Integer
    >>> @mathy.action(accepts=Array(Integer), returns=Integer)
    ... def add(numbers):
    ...     return sum(numbers)
    ... 
    >>>

The function used in the action is perfectly usable:

.. code:: python

    >>> add([1, 2, 3])
    6

But now there is another way of accessing it:

.. code:: python

    >>> mathy.actions.sum([1, 2, 3])
    6

Both *accepts* and *returns* are optional. If no accepts schema is provided,
the action will take no input data, and if the returns schema is not provided,
the action will return nothing when it completes.

Normally, the action function is expected to take a single non-keyword
argument. If your action needs to take multiple arguments, use the Teleport
:class:`~cosmic.legacy_teleport.Struct` type:

.. code:: python

    @mathy.action(accepts=Struct([
        required(u'numerator', Integer),
        required(u'denominator', Integer),
    ]), returns=Integer)
    def divide(numerator, denominator):
        return numerator / denominator

This may be called as:

.. code:: python

    >>> mathy.actions.divide(numerator=10, denominator=5)
    2

.. _guide-models:

REST via Models
---------------

Models are data type definitions attached to an API, they use Teleport schemas
to describe their data.

Let's take a look at the model object:

.. code:: python

    from cosmic.api import API
    from cosmic.models import BaseModel

    places = API('places')

    @places.model
    class Address(BaseModel):
        properties = [
            required(u"number", Integer),
            optional(u"street", String),
            optional(u"city", String)
        ]

As you can see, a model class should inherit from
:class:`~cosmic.models.BaseModel` and in order to register it with an API, you
must use the :meth:`~cosmic.api.API.model` decorator on it. Once a model has 
been registered with an API, it becomes accessible as part of the
:data:`~cosmic.api.API.models` namespace, for example ``places.models.Address``.

Once registered with an API, a model becomes available in the
:data:`~cosmic.api.API.models` namespace. The beauty of this namespace
is that it is identical on the client and server.

Models can be used to create REST-ful endpoints. A model roughly corresponds
to a database table. If you want to give clients access to *objects* of the
data type defined by the model, you also need to define a set of CRUD methods
that Cosmic will turn into HTTP endpoints.

The *links* parameter describes relationships between models. A link from one
model to another is similar to a foreign key in a relational database.

Links are defined similarly to properties:

.. code:: python

    places = API('places')

    @places.model
    class City(BaseModel):
        properties = [
            optional(u"name", String)
        ]

    @places.model
    class Address(BaseModel):
        properties = [
            required(u"number", Integer),
            required(u"street", String),
        ]
        links = [
            required(u"city", City)
        ]

These models are merely data type definitions, they do not have REST endpoints
because they are not connected to any database.

If apart from defining a data type we also want to provide access to a
collection of objects of this data type, there are 5 methods that Cosmic
allows us to override. These methods correspond to 5 HTTP endpoints.
Methods must be declared by adding their name to the
:data:`~cosmic.models.BaseModel.methods` property on the model class.

get_by_id
`````````

.. seealso::

    :class:`~cosmic.http.GetByIdEndpoint` for HTTP spec.

The simplest method to implement is
:meth:`~cosmic.models.BaseModel.get_by_id`. It takes a single parameter (an id
is always a string) and returns a dict representing the object. If the object
doesn't exist, it must raise :exc:`~cosmic.exceptions.NotFound`.

.. code:: python

    from cosmic.exceptions import NotFound

    places = API('places')

    @places.model
    class City(BaseModel):
        methods = ["get_by_id", "create", "update", "delete", "get_list"]
        properties = [
            optional(u"name", String)
        ]

        @classmethod
        def get_by_id(cls, id):
            try:
                return cities[id]
            except KeyError:
                raise NotFound

    cities = {
        "0": {"name": "Toronto"},
        "1": {"name": "San Francisco"},
    }

As you can see, Cosmic doesn't care what kind of database you use, as long as
the method returns the right value. Now if we want to use this method, we can
do, on the client or server:

.. code:: python

    >>> city = places.models.City.get_by_id("1")
    {"name": "San Francisco"}

create
``````

.. seealso::

    :class:`~cosmic.http.CreateEndpoint` for HTTP spec.

The :meth:`~cosmic.models.BaseModel.create` method takes a *patch* (a model
representation where every field is optional) and returns a tuple with the new
id and representation:

.. code:: python

    @classmethod
    def create(cls, patch):
        new_id = str(len(cities))
        cities[new_id] = patch
        return new_id, cities[new_id]

update
``````

.. seealso::

    :class:`~cosmic.http.UpdateEndpoint` for HTTP spec.

The :meth:`~cosmic.models.BaseModel.update` method takes an id and patch and
either applies the patch, returning the new representation, or raises
:exc:`~cosmic.exceptions.NotFound`.

.. code::

    @classmethod
    def update(cls, id, patch):
        if id not in cities:
            raise NotFound
        cities[id] = patch
        return cities[id]

delete
``````

.. seealso::

    :class:`~cosmic.http.DeleteEndpoint` for HTTP spec.

The :meth:`~cosmic.models.BaseModel.delete` method, upon deleting the object,
returns nothing. It raises  :exc:`~cosmic.exceptions.NotFound` if the object
does not exist:

.. code::

    @classmethod
    def delete(cls, id):
        if id not in cities:
            raise NotFound
        del cities[id]

.. _get_list:

get_list
````````

.. seealso::

    :class:`~cosmic.http.GetListEndpoint` for HTTP spec.

The :meth:`~cosmic.models.BaseModel.get_list` method takes keyword arguments
as specified by the *query_fields* model property. This schema is used to
serialize them into a URL query string with the help of
:class:`~cosmic.types.URLParams`.

.. code::

    query_fields = [
        optional(u"country", String)
    ]

    @classmethod
    def get_list(cls, country=None):
        if country is None:
            return cities.items()
        elif country == "Canada":
            return [("0", cities["0"])]
        elif country == "USA":
            return [("1", cities["1"])]
        else:
            return []

The return value of this function is a (possibly empty) list of tuples where
the first element is the object id and the second is the object representation.

You are free to invent your own pagination schemes using custom query fields.

Often it will be useful to return metadata along with the items, for example,
the total count if the list is paginated, or a timestamp. You can specify this
by including the :data:`list_metadata` attribute.

.. code:: python

    list_metadata = [
        required(u"total_count", Integer)
    ]

    @classmethod
    def get_list(cls):
        metadata = {"total_count": len(cities)}
        return (cities.items(), metadata)

As you can see, when :data:`list_metadata` is specified, the return value
of :meth:`get_list` is a tuple, where the first item is the list, and the
second is a dict containing the metadata.

.. _guide-serving:

Serving
-------

For development, :meth:`~cosmic.api.API.run` is fine, but for production, you
should use a WSGI server such as `Gunicorn <http://gunicorn.org/>`_. In order
to do this, use :class:`~cosmic.http.Server` to expose the raw WSGI
application.

.. code:: python

    from cosmic.api import API
    from cosmic.http import Server
    from cosmic.types import *

    words = API('words')


    @words.action(accepts=String, returns=String)
    def pluralize(word):
        if word.endswith('y'):
            return word[:-1] + 'ies'
        else:
            return word + 's'

    wsgi_app = Server(words).wsgi_app

Now you can run it in your favorite web server:

.. code:: bash

    $ gunicorn -b 127.0.0.1:5001 words:wsgi_app

.. _guide-authentication:

Authentication
--------------

Currently, Cosmic does not provide a standard authentication mechanism. It
does provide powerful HTTP hooks which can be used to implement different
authentication schemes.

On the server, you can use standard WSGI middleware, and you can subclass
:class:`~cosmic.http.Server`:

.. code:: python

    from flask import make_response
    from cosmic.api import API
    from cosmic.http import Server, error_response

    planetarium = API("planetarium")

    class PlanetariumServer(Server):

        def view(self, endpoint, request, **url_args):
            if request.headers.get('Authorization', None) != 'secret':
                return error_response("Unauthorized", 401)
            return super(PlanetariumServer, self).view(endpoint, request, **url_args)

    wsgi_app = PlanetariumServer(planetarium).wsgi_app

On the client, we can subclass :class:`~cosmic.client.APIClient` to add
authentication info to each request:

.. code:: python

    from cosmic.client import APIClient

    class PlanetariumClient(APIClient):
        base_url = 'https://api.planetarium.com'

        def build_request(self, endpoint, *args, **kwargs):
            request = super(APIClient, self).build_request(endpoint, *args, **kwargs)
            request.headers["Authorization"] = "secret"
            return request

    planetarium = PlanetariumClient()

Storing Global Data
-------------------

In every web application some data must be available globally during request
processing, for example, the database connection or the currently
authenticated user. Some frameworks, like
`Django <https://www.djangoproject.com/>`_, attach this data to the request
object which gets passed around explicitly. Others, like
`Flask <http://flask.pocoo.org/>`_, store it in a thread-local object. Cosmic
borrows the latter approach, offering you a simple dictionary-like class for
this purpose: :class:`~cosmic.globals.ThreadLocalDict`.

.. code:: python

    from cosmic.globals import ThreadLocalDict

    g = ThreadLocalDict()

What happens when we try to set a value?

.. code:: python

    >>> g = ThreadLocalDict()
    >>> g['foo'] = 1
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/lib/python2.7/UserDict.py", line 24, in __setitem__
        def __setitem__(self, key, item): self.data[key] = item
      File "cosmic/globals.py", line 87, in data
        raise ThreadLocalMissing()
    cosmic.exceptions.ThreadLocalMissing

Uh oh. Why wasn't a thread-local created when we created a
:class:`~cosmic.globals.ThreadLocalDict`? Unlike regular Python
`thread-locals
<https://docs.python.org/2/library/threading.html#threading.local>`_, Cosmic
thread-locals don't clean themselves up after a thread finishes. This is a
necessary sacrifice in order to make them work with greenlets. Because of this,
a thread-local's lifetime is controlled explicitly with the
:func:`~cosmic.globals.thread_local` context manager or, more conveniently,
with :func:`~cosmic.globals.thread_local_middleware`.

.. code:: python

    >>> with thread_local():
    ...     g['foo'] = 1
    ...     print g['foo']
    ...
    1

Now we can use it to store the current user:

.. code:: python

    class CustomServer(Server):

        def view(self, endpoint, request, **url_args):
            secret = request.headers.get('Authorization', None)
            if secret == '12345':
                g['current_user'] = 'bob@example.com'
            elif secret == 'qwert':
                g['current_user'] = 'alice@example.com'
            else:
                return error_response("Unauthorized", 401)
            return super(CustomServer, self).view(endpoint, request, **url_args)

For testing, it may be necessary to call some functions with a predefined
*context*, for example, call a function on behalf of Bob. For this, use the
:meth:`~cosmic.globals.ThreadLocalDict.swap` method:

.. code:: python

    with g.swap({'current_user': 'dick@example.com'}):
        assert g['current_user'] == 'dick@example.com'

The value will be swapped when entering the :keyword:`with` block, and swapped
back when exiting it.

