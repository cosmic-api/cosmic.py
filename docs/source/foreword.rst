Foreword
========

Motivation
----------

You cannot escape writing API clients. On the provider side, the API library
or framework serves as glue between business code and HTTP. On the consumer
side, the burden of gluing HTTP to business logic lies on the shoulders of the
developer.

Writing a client for every API/language combination is a tremendous amount of
work (``O(n^2)``), only the most popular APIs and the most popular languages
have clients written for them. Cosmic brings the amount of work down to
``O(n)`` by specifying a way of building universal clients. Such a client is
built from the description of an API in the form of a JSON spec.

If you port Cosmic to a new language, you do the equivalent of writing a
client in for every existing Cosmic API. If you use Cosmic to build an API,
you get a number of clients for free. New client ports motivate developers
to pick Cosmic as a server-side API framework. New Cosmic APIs motivate
developers to write new clients.

As for the API spec, our approach differs from something like `Swagger
<https://developers.helloreverb.com/swagger/>`_ as we are not trying to
describe an API in low-level detail (down to the URLs and methods). Instead,
the JSON spec of a Cosmic API tries to be high-level and semantic.

We are tired of HTTP, we are tired of arguments around how to structure URLs,
how to serialize query parameters, which headers to include and which codes
to return. We believe that these questions simply *don't matter*. Pick a way
and move on to more important questions. Or better yet, let Cosmic make those
decisions and take advantage of the reward: cheap API clients.

REST and RPC
------------

* REST assigns names (URIs) to things (resources).
* REST provides a uniform interface to manipulate these resources.
* These resources are often rows in a database.
* Things not stored in a table can be modeled as resources too.
* RPC is remote procedure calls.
* RPC is okay, unless it is used to implement resource manipulation.
* RPC can complement primarily REST-ful APIs

Architecture
------------

* Cosmic is a layer that sits between business code and HTTP.
* Cosmic client is a Cosmic server that has been serialized and deserialized.
* Because of this, Cosmic client and server objects behave almost identically.
* Where a Cosmic server will call a user-defined function, a Cosmic client will call the Cosmic server.
* [endpoint diagram]
* Within Cosmic, HTTP is treated as a serialization layer.
* Server: parse request, make response (Flask)
* Client: make request, parse response (Requests)
* These four functions are intimately related and together define an endpoint.
* Data enters and exits an endpoint in native form, no HTTP must leak through.

Built on Teleport
-----------------

* Cosmic makes heavy use of Teleport, our type system which we use for serialization, validation and generating documentation.
* Teleport is JSON.
* Teleport provides common types and lets you define your own.
* Teleport types are composable.
* Some object (notably the API) are implemented as Teleport types.
* Teleport schemas are serializeable, which lets us serialize things like function definitions.

Built on Flask
--------------

* For a lot of HTTP-related functions, the Python implementation of Cosmic relies on Flask.
* A Cosmic API server creates a Flask app from scratch.
* You should avoid manipulating this app.
* Some knowledge of Flask may be necessary, like flask.request and flask.g

