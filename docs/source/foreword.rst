Foreword
========

Motivation
----------

* Writing API clients in inescapable.
* If you don't use an API client you end up writing your own.
* For well-known APIs, a client is written in every well-known language (A x L clients).
* Why isn't there a universal client?
* Because every API is different.
* Why is every API different?
* Because developers are forced to make low-level design choices.
* Cosmic APIs are similar because Cosmic takes responsibility for these choices.
* By porting Cosmic to a new language, you do the equivalent of writing numerous API clients.

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

