Overview
========

Before we dig in, here is a high-level overview of Cosmic.

REST and RPC
------------

The definition of `REST
<http://en.wikipedia.org/wiki/Representational_state_transfer>`_ is a
controversial subject. For our purposes, these are the key elements:

* Objects are assigned unique URLs.
* These URLs are used to link objects together.
* Objects are manipulated by a set of standard methods (`CRUD
  <http://en.wikipedia.org/wiki/Create,_read,_update_and_delete>`_).

It is fairly straightforward to create a REST API from a database table, but
other kinds of information can be expressed with REST as well. In general it
is a good idea to try, and fall back on `RPC
<http://en.wikipedia.org/wiki/Remote_procedure_call>`_ only if REST is clearly
a bad fit.

RPC stands for "remote procedure call". It is a simple interface where a
client sends a request to call a remote function with certain parameters and
gets the return value of the function in the response. You might find many
discussions online that are framed as "REST vs RPC", but in reality they are
tools that complement each other.

Architecture
------------

Cosmic is a layer that sits between business code and HTTP. The client and
server component are perfectly symmetrical, so similar that they are
represented by the same interface, :class:`~cosmic.api.BaseAPI`. On the server,
an instance of its subclass, :class:`~cosmic.api.API`, gets populated with
user-defined handler functions, bits of documentation and other metadata. On
the client, another subclass, :class:`~cosmic.client.APIClient` gets created
automatically from a spec, the handler functions being HTTP calls.

The API spec is represented in JSON and served from a standard location:
``/spec.json``.

Cosmic's simplicity comes from treating HTTP as nothing more than an elaborate
serialization scheme for function inputs and outputs. Because different types
of REST calls require different HTTP methods and return calls, Cosmic defines
several *endpoints*, subclasses of :class:`~cosmic.http.Endpoint`.

Each endpoint defines the methods :meth:`build_request`, :meth:`parse_request`,
:meth:`build_response` and :meth:`parse_response`. These methods abstract away
all HTTP nonsense so the rest of Cosmic (and, of course, your code) deals with
purely native data.

..  TODO [endpoint diagram]

Built on Teleport
-----------------

.. warning::

    This version of Cosmic relies on an out-of-date version of Teleport.
    Until Cosmic is ported to Teleport 0.3, it includes a copy of Teleport
    in the :mod:`cosmic.legacy_teleport`, so you can install it side-by-side
    with an up-to-date version of Teleport.

.. seealso::

    The `Teleport documentation <http://teleport-json.org>`_ is worth a
    look if you are getting started with Cosmic.

Teleport is our very own tiny library that is used for JSON serialization,
validation, and generating documentation. At first this might seem like an odd
set of features for a library, but they come quite naturally from the fact
that Teleport is essentially a very simple static type system. All information
that gets carried between Cosmic clients and servers is statically typed with
the help of Teleport.

Teleport is implemented as a collection of composable type objects. The
composition of these objects mirrors the data it is meant to serialize and
validate. One important feature of Teleport is that these type definitions, the
schema, is also serializable. This makes it possible to use Teleport to
serialize model properties, function definitions, and indeed, the whole API
spec.

Teleport makes it easy to define custom types, a feature used by Cosmic.

The Teleport docs will teach you to import from the :mod:`teleport` module:

.. code:: python

    from teleport import *

In Cosmic, you should import from :mod:`cosmic.types`:

.. code:: python

    from cosmic.types import *

.. _hal:

Hypermedia with JSON HAL
------------------------

`JSON HAL <http://stateless.co/hal_specification.html>`_ is a compact
specification for linking REST-ful resources as well as returning multiple
embedded resources in one call (this is used by the :ref:`get_list` endpoint).
Note that HAL recommends ``application/hal+json`` for the *Content-Type*
header, but currently Cosmic responds only to ``application/json``.
