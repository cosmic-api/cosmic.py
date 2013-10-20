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

    >>> from teleport import Integer
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

.. TODO: Executing the same action on the client

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

.. TODO: When accepts is a Struct, you can pass in values as kwargs.

REST via Models
---------------

Models are used to create REST-ful endpoints. A model roughly corresponds to a
database table. Most basically, a model defines a datatype. If you want to
give clients access to *objects* of this datatype, you also need to define a
set of CRUD methods that Cosmic will turn into HTTP endpoints.

Here is the the Teleport schema of a model:

.. code:: python

    Struct([
        optional("data_schema", Schema),
        required("links", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ]))),
        required("query_fields", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ])))
    ])

The first parameter, *data_schema* is the type definition that describes the
model data. If your model represents a database table, the *data_schema* could
be a struct with parameters that correspond to the table's columns. Currently,
Cosmic expects it to be a struct, but this restriction may be lifted later.

The *links* parameter describes relationships between models. A link from one
model to another is similar to a foreign key in a relational database. The
last parameter, *query_fields* is used to describe how a collection of objects
can be filtered. See :ref:`get_list`.

Before we get to linking and filtering, let's take a look at the model object:

.. code:: python

    from cosmic.api import API
    from cosmic.models import BaseModel

    places = API('places')

    @places.model
    class Address(BaseModel):
        properties = [
            required("number", Integer),
            required("street", String),
            required("city", String)
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

    >>> sesame31 = places.models.Address(number=31, street="Sesame")
    >>> sesame31.number
    31
    >>> sesame31.street
    "Sesame"

This means that you can add methods to your models, or, if you have existing
classes that you want to turn into Cosmic models, you can do so simply by
inheriting from :class:`~cosmic.models.BaseModel`, using the
:meth:`~cosmic.api.API.model` decorator and adding a schema.

A model is actually a Teleport type::

    >>> places.models.Address.to_json(sesame31)
    {
        u"number": 31,
        u"street": "Sesame"
    }

Links are defined similarly to properties::

    places = API('places')

    @places.model
    class City(BaseModel):
        properties = [
            optional("name", String)
        ]

    @places.model
    class Address(BaseModel):
        properties = [
            required("number", Integer),
            required("street", String),
        ]
        links = [
            required("city", City)
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
            optional("name", String)
        ]

        @classmethod
        def get_by_id(cls, id):
            if id in cities:
                city = cities[id]
                city.id = id
                return city
            else:
                return None

    cities = {
        "0": City(name="Toronto"),
        "1": City(name="San Francisco"),
    }

As you can see, Cosmic doesn't care what kind of database you use, as long as
the method returns the right value. Now if we want to use this method, we can
do::

    >>> city = places.models.City.get_by_id("1")
    >>> city.name
    "San Francisco"

.. TODO: [HTTP spec]

.. _get_list:

get_list *
``````````

.. seealso::

    :class:`~cosmic.http.GetListEndpoint` for HTTP spec.

* Takes kwargs, determined by query_params attribute of the model.
* Kwargs get deserialized into URL params.
* Array gets unrolled into repeating params, otherwise it's URL-encoded JSON.
* Returns a possibly empty list of model instances.

save (create) *
```````````````

.. seealso::

    :class:`~cosmic.http.CreateEndpoint` for HTTP spec.

* Create is triggered when save is called on a model without an id.
* When the call completes, an id will be set.

save (update) *
```````````````

.. seealso::

    :class:`~cosmic.http.UpdateEndpoint` for HTTP spec.

* Update is triggered when save is called on a model with an id.

delete *
````````

.. seealso::

    :class:`~cosmic.http.DeleteEndpoint` for HTTP spec.

* After the call completes, the model object remains but becomes invalid.

Authentication *
----------------

* Currently, Cosmic does not provide a standard authentication mechanism.
* Authentication is done by making ClientHooks and ServerHooks.
* To ask for credentials, override ServerHook.build_response
* To supply credentials, override ClientHook.build_request
* To check credentials, override ServerHook.parse_request
* Authentication error should be raised when invalid credentials are provided.
* An authorization error can be raised from anywhere in the code.
* By overriding ClientHook.call, you can make the request repeat once credentials have been found.
* This will let the client continue seamless operation.

Deployment on Heroku *
----------------------

* Assuming you have a Heroku account
* $ heroku login
* Add cosmic to requirements.txt
* Create Procfile
* [example app]
* $ git init && git commit
* Heroku create
* $ git push origin master

