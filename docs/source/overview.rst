Overview
========

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
        required("actions", OrderedMap(Function)),
        required("models", OrderedMap(Struct([
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
        ])))
    ])

RPC via Actions
---------------

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
.. TODO: [HTTP spec]

REST via Models
---------------

Models are REST-ful resources. A model roughly corresponds to a database
table. Each model has several optional HTTP endpoints.

* Models define two things: a datatype and (optionally), a set of entities, relationships between them and methods of manipulating them.
* Model schema is always a Struct (the datatype).
* Model instances are actual instances of the model class.
* API clients have models stored in my_api.models.Bar.
* Model relationships are defined as links.
* Many-to-many relationships should be defined with a separate relationship model.
* Model can implement 5 methods below.
* You can specify which by settings the methods property.

get_by_id
`````````

* An id is always a string.
* Function returns a model instance or None.
* [HTTP spec]

get_list
````````

* Takes kwargs, determined by query_params attribute of the model.
* Kwargs get deserialized into URL params.
* Array gets unrolled into repeating params, otherwise it's URL-encoded JSON.
* Returns a possibly empty list of model instances.
* [HTTP spec]

save (create)
`````````````

* Create is triggered when save is called on a model without an id.
* When the call completes, an id will be set.
* [HTTP spec]

save (update)
`````````````

* Update is triggered when save is called on a model with an id.
* [HTTP spec]

delete
``````

* After the call completes, the model object remains but becomes invalid.
* [HTTP spec]

Authentication
--------------

* Currently, Cosmic does not provide a standard authentication mechanism.
* Authentication is done by making ClientHooks and ServerHooks.
* To ask for credentials, override ServerHook.build_response
* To supply credentials, override ClientHook.build_request
* To check credentials, override ServerHook.parse_request
* Authentication error should be raised when invalid credentials are provided.
* An authorization error can be raised from anywhere in the code.
* By overriding ClientHook.call, you can make the request repeat once credentials have been found.
* This will let the client continue seamless operation.

Deployment on Heroku
--------------------

* Assuming you have a Heroku account
* $ heroku login
* Add cosmic to requirements.txt
* Create Procfile
* [example app]
* $ git init && git commit
* Heroku create
* $ git push origin master

