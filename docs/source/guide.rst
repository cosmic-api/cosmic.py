Guide
=====

Installation
------------

Assuming you are running Linux or OS X and are familiar with `pip <http://www.pip-installer.org/en/latest/quickstart.html>`_, installation is as easy as:

.. code:: bash

   pip install cosmic

If you are not yet familiar with `virtualenv
<http://www.virtualenv.org/en/latest/>`_, it is an indespensible tool for
Python development. It lets you create isolated Python environments for every
project you are working on. This means that different projects can depend on
different versions of the same library.

If you would like to work on the bleeding edge of Cosmic development, you 
can clone the repo using git:

.. code:: bash
    
    git clone https://github.com/cosmic-api/cosmic.py.git cosmic-py

Then to install the current version (ideally you want to do this in a
virtualenv):

.. code:: bash

    cd cosmic-py
    python setup.py develop

What's in an API?
-----------------

A web API is:

* An interface through which a server can share data and functionality with
  clients over the internet.
* A component of the server architecture that glues the database and business
  logic to HTTP.

In the context of Cosmic, an API is represented, unsurprisingly, by an
instance of the :class:`~cosmic.api.API` class. What is interesting, however,
is that this object is serializable to JSON. The JSON form of an API is the
API spec.

You may find it strange that we say "serialize an API" when we could simply
say "generate an API spec". The reason we say this is to highlight the fact
that an API is simply a Teleport datatype. The API object on the server and
the API object on the client are instances of the same class, in fact, they
are almost identical. The difference is that for every server endpoint, there
is a hook into the server's database or business logic, whereas each client
endpoint replaces this with an HTTP call.

Let's serialize a trivial API. Note that :meth:`to_json` is a standard
Teleport method::

    >>> from cosmic.api import API
    >>> mathy = API("trivia", homepage="http://example.com")
    >>> API.to_json(mathy)
    {
        u'name': 'mathy',
        u'homepage': 'http://example.com',
        u'actions': {u'map': {}, u'order': []},
        u'models': {u'map': {}, u'order': []}
    }

Let's take a look at what's inside.

First, there is the basic metadata: the API *name* and *homepage*. The name of
the API should be unique. Though this is not yet enforced by Cosmic, we plan on
indexing Cosmic APIs on our website in which case it will become a requirement.

Then, the API spec contains descriptions of *actions* and *models*. These will
be explained in detail in the next two sections. Here is the Teleport schema
for the API type:

.. code:: python

    Struct([
        required("name", String),
        optional("homepage", String),
        required("actions", OrderedMap(Action)),
        required("models", OrderedMap(Model))
    ])

Client and Server
-----------------

In Cosmic, the same :class:`~cosmic.api.API` class is used for the API server
and the API client. In fact, the server and the client objects behave almost
identically. After you run your server component, you can build the client in
a single line of code::

    >>> myapi = API.load('http://localhost:5000/spec.json')

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

    >>> from cosmic.types import Integer
    >>> @mathy.action(accepts=Integer, returns=Integer)
    ... def square(n):
    ...     return n ** 2
    ... 
    >>>

The function used in the action is perfectly usable:

.. code:: python

    >>> square(2)
    4

But now there is another way of accessing it:

.. code:: python

    >>> mathy.actions.square(2)
    4

And from the client, it is accessed identically::

    >>> mathy = API.load('http://localhost:5000/spec.json')
    >>> mathy.actions.square(2)
    4

Now that the action has been registered, it becomes part of the spec:

.. code:: python

    >>> API.to_json(mathy)
    {
        u'name': 'mathy',
        u'homepage': 'http://example.com',
        u'actions': {
            u'map': {
                u'square': {
                    u'returns': {'type': 'Integer'},
                    u'accepts': {'type': 'Integer'}
                }
            },
            u'order': [u'square']
        },
        u'models': {u'map': {}, u'order': []}
    }

If you are not yet familiar with Teleport, you might be wondering what is the
purpose of the ``name`` and ``order`` items in the ``actions`` object above.
This is the way Teleport uses JSON to represent an ordered mapping. Both actions
and models are contained in the Teleport's :class:`~teleport.OrderedMap` type.

Both *accepts* and *returns* are optional. If no accepts schema is provided,
the action will take no input data, and if the returns schema is not provided,
the action will return nothing when it completes.

Normally, the action function is expected to take a single non-keyword
argument. If your action needs to take multiple arguments, use the Teleport
:class:`~teleport.Struct` type::

    @mathy.action(accepts=Struct([
        required(u'numerator', Integer),
        required(u'denominator', Integer),
    ]), returns=Integer)
    def divide(numerator, denominator):
        return numerator / denominator

This may be called remotely as::

    >>> mathy = API.load('http://localhost:5000/spec.json')
    >>> mathy.actions.divide(numerator=10, denominator=5)
    2

Models as Data Types
--------------------

Models are data type definitions attached to an API, they use Teleport schemas
to describe their data. In the API spec, a model is described with the following
schema:

.. code:: python

    Struct([
        optional(u"data_schema", Schema),
        required(u"links", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ]))),
        required(u"query_fields", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ])))
    ])

The first parameter, *data_schema* is the type definition that describes the
model data. If your model represents a database table, the *data_schema* could
be a struct with parameters that correspond to the table's columns. Currently,
Cosmic expects it to be a struct, but this restriction may be lifted later.

The *links* parameter describes relationships between models. The last
parameter, *query_fields* is used to describe how a collection of objects can
be filtered. Both of these are used by Cosmic to create REST endpoints.

Before we get to linking and filtering, let's take a look at the model object:

.. code:: python

    from cosmic.api import API
    from cosmic.models import BaseModel

    places = API('places')

    @places.model
    class Address(BaseModel):
        properties = [
            required(u"number", Integer),
            required(u"street", String),
            required(u"city", String)
        ]

As you can see, a model class should inherit from
:class:`~cosmic.models.BaseModel` and in order to register it with an API, you
must use the :meth:`~cosmic.api.API.model` decorator on it. Once a model has 
been registered with an API, it becomes accessible as part of the
:data:`~cosmic.api.API.models` namespace, for example ``places.models.Address``.

If you try to serialize this API, you will see the model made it into the spec:

.. code:: python

    >>> API.to_json(places)
    {
        u'name': u'places',
        u'actions': { u'map': {}, u'order': [] },
        u"models": {
            u"map": {
                u"Address": {
                    u"data_schema": {
                        u'type': u"Struct",
                        u"param": {
                            u"map": {
                                u"number": {
                                    u"required": True,
                                    u"schema": {u"type": u"Integer"}
                                },
                                u"street": {
                                    u"required": True,
                                    u"schema": {u"type": u"String"}
                                },
                                u"city": {
                                    u"required": False,
                                    u"schema": {u"type": u"String"}
                                }
                            },
                            u"order": [u"number", u"street", u"city"]
                        }
                    },
                    u"links": { u"map": {}, u"order": [] },
                    u"query_fields": { u"map": {}, u"order": [] }
                }
            },
            u"order": [u"Address"]
        }
    }

There is a good reason model definitions are in the form of classes.
In Cosmic, the objects that the model defines are represented by actual
instances of the model class::

    >>> sesame31 = Address(number=31, street="Sesame")
    >>> sesame31.number
    31
    >>> sesame31.street
    "Sesame"

This means that you can easily add methods to your models.

Furthermore, a model is actually a Teleport type::

    >>> Address.to_json(sesame31)
    {
        u"number": 31,
        u"street": "Sesame"
    }

:class:`~cosmic.models.BaseModel` inherits from Teleport's
:class:`~teleport.BasicWrapper`. If you have existing classes that you want to
turn into Cosmic models, you can do so quite easily. (See `Creating Custom
Types </docs/teleport/python/latest/index.html#creating-custom-types>`_ in
Teleport.)

Once registered with an API, a model becomes available in the
:data:`~cosmic.api.API.models` namespace. The beauty of this namespace
is that it is identical on the client and server. Here is how to create
an :class:`Address` on the client::

    >>> places = API.load('http://localhost:5000/spec.json')
    >>> elm13 = places.models.Address(number=13, street="Elm")
    >>> elm13.number
    13

REST via Models
---------------

Models can be used to create REST-ful endpoints. A model roughly corresponds
to a database table. If you want to give clients access to *objects* of the
data type defined by the model, you also need to define a set of CRUD methods
that Cosmic will turn into HTTP endpoints.

The *links* parameter describes relationships between models. A link from one
model to another is similar to a foreign key in a relational database.

Links are defined similarly to properties::

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

And referenced similarly to properties::

    >>> toronto = places.models.City(name="Toronto")
    >>> spadina147 = self.places.models.Address(
    ...     number=147,
    ...     street="Spadina",
    ...     city=toronto)
    >>> spadina147.city.name
    "Toronto"

These models are merely data type definitions, they do not have REST endpoints
because they are not connected to any database. How do you know? You can try
this::

    >> spadina147.id is None
    True

If apart from defining a data type we also want to provide access to a
collection of objects of this data type, there are 4 methods that Cosmic
allows us to override. These methods correspond to 5 HTTP endpoints. Cosmic
decides whether the endpoints should be created or not based on whether the
methods have been defined. This behavior can be overridden by setting the
:data:`~cosmic.models.BaseModel.methods` property on the model class.

get_by_id
`````````

.. seealso::

    :class:`~cosmic.http.GetByIdEndpoint` for HTTP spec.

The simplest method to implement is :meth:`get_by_id`. It takes a single
parameter (an id is always a string) and returns a model class instance
(or ``None``, if no model is found)::

    places = API('places')

    @places.model
    class City(BaseModel):
        properties = [
            optional(u"name", String)
        ]

        @classmethod
        def get_by_id(cls, id):
            if id in cities:
                return cities[id]
            else:
                return None

    cities = {
        "0": City(name="Toronto", id="0"),
        "1": City(name="San Francisco", id="1"),
    }

As you can see, Cosmic doesn't care what kind of database you use, as long as
the method returns the right value. Now if we want to use this method, we can
do::

    >>> city = places.models.City.get_by_id("1")
    >>> city.name
    "San Francisco"
    >>> places.models.City.get_by_id("5") is None
    True

save
````

.. seealso::

    :class:`~cosmic.http.CreateEndpoint` and
    :class:`~cosmic.http.UpdateEndpoint` for HTTP spec.

The :meth:`~cosmic.models.BaseModel.save` method is actually used for two
different operations: saving and updating. On the HTTP level they are two
distinct HTTP endpoints.

.. code::

    @places.model
    class City(BaseModel):
        properties = [
            optional(u"name", String)
        ]

        def save(self):
            if self.id is None:
                # Create new id
                self.id = str(len(cities))
            cities[self.id] = self

When implementing this function on the server side, you should check for the
model's *id* property. If set, you should update, if not set, you should save,
creating a new id in the process. On the client side, whether id is set will
determine which HTTP call to make. If :meth:`save` is called on a model with
no id, then if the call completes successfully, an id will be set::

    >>> city = City(name="Moscow")
    >>> city.id is None
    True
    >>> city.save()
    >>> city.id
    "2"

To add extra validation to a model, you can override the
:meth:`~class.model.BaseModel.validate` method. This method gets called after
the model schema has been used to deserialize the data and before the
model object gets instantiated. Here is a :meth:`validate` method for
:class:`City`::

    @classmethod
    def validate(cls, datum):
        if datum[u"name"][0].islower():
            raise ValidationError("Name must be capitalized", datum["name"])

A :exc:`ValidationError` will be raised if you try to save an invalid model
from a remote client:

    >>> places = API.load('http://localhost:5000/spec.json')
    >>> moscow = places.models.City(name="moscow")
    >>> moscow.save()
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/api.py", line 85, in save
        inst = self.__class__._list_poster(self)
      File "cosmic/http.py", line 287, in __call__
        return self.api.client_hook.call(self, *args, **kwargs)
      File "cosmic/http.py", line 27, in call
        return self.parse_response(endpoint, res)
      File "cosmic/http.py", line 33, in parse_response
        return endpoint.parse_response(res)
      File "cosmic/http.py", line 596, in parse_response
        res = super(CreateEndpoint, self).parse_response(res)
      File "cosmic/http.py", line 273, in parse_response
        raise ValidationError(r['json'].datum.get('error', ''))
    teleport.ValidationError: Name must be capitalized: u'moscow'

delete
``````

.. seealso::

    :class:`~cosmic.http.DeleteEndpoint` for HTTP spec.

The :meth:`~cosmic.models.BaseModel.delete` method, upon deleting the object,
returns nothing.

.. code::

    @places.model
    class City(BaseModel):
        properties = [
            optional(u"name", String)
        ]

        @classmethod
        def get_by_id(cls, id):
            if id in cities:
                return cities[id]
            else:
                return None

        def delete(self):
            del cities[self.id]

After being called, the instance will still be there but it should be
considered invalid. If you try to fetch the object with the deleted id using
:meth:`~cosmic.models.BaseModel.get_by_id`, ``None`` will be returned.

.. code::

    >>> city = places.models.City.get_by_id("0")
    >>> city.delete()
    >>> places.models.City.get_by_id("0") is None
    True

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

    @places.model
    class City(BaseModel):
        properties = [
            optional(u"name", String)
        ]
        query_fields = [
            optional(u"country", String)
        ]

        @classmethod
        def get_list(cls, country=None):
            if country is None:
                return cities.values()
            elif country == "Canada":
                return [cities[0]]
            elif country == "USA":
                return [cities[1]]
            else:
                return []

The return value of this function is a (possibly empty) list of model
instances::

    >>> l = places.models.City.get_list()
    >>> len(l)
    2
    >>> l = places.models.City.get_list(country="Canada")
    >>> len(l)
    1
    >>> l[0].name
    "Toronto"
    >>> places.models.City.get_list(country="Russia")
    []

You are free to invent your own pagination schemes using custom query fields.

.. _guide-authentication:

Authentication
--------------

Currently, Cosmic does not provide a standard authentication mechanism. It
does provide powerful HTTP hooks which can be used to implement different
authentication schemes.

On the server, you can override your API's :data:`~cosmic.API.server_hook`
property with an instance of a custom subclass
:class:`~cosmic.http.ServerHook`. On the client, you can override
:data:`~cosmic.API.client_hook` with an instance of a subclass of
:class:`~cosmic.http.ClientHook`. These classes are symmetrically similar,
each of them provides three methods to override. Let's override the
:meth:`~cosmic.http.ServerHook.view` method of
:class:`~cosmic.http.ServerHook` to enable our API to verify user credentials.

.. code::

    from flask import make_response
    from cosmic.api import API
    from cosmic.http import ServerHook

    planetarium = API("planetarium")

    class CustomServerHook(ServerHook):

        def view(self, endpoint, request, **url_args):
            if not endpoint.never_authenticate:
                if request.headers.get('Authorization', None) != 'secret':
                    return make_response("", 401, {'WWW-Authenticate': 'MyAuth'})
            return super(CustomServerHook, self).view(endpoint, request, **url_args)

    planetarium.server_hook = CustomServerHook()

In this example, we check for credentials provided in the *Authorization*
header. If they are missing or wrong, we return a 401 response, asking for
authentication via the *WWW-Authenticate* header.

Now let's implement a hook on the client to add credentials to every request
that needs it.

.. code::

    from cosmic.api import API
    from cosmic.http import ClientHook

    planetarium = API.load('https://api.planetarium.com/spec.json')

    class CustomClientHook(ClientHook):

        def build_request(self, endpoint, *args, **kwargs):
            request = super(Hook, self).build_request(endpoint, *args, **kwargs)
            request.headers["Authorization"] = "secret"
            return request

This should be enough to get authentication working between client and server.

