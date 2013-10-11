Overview
========

Installation
------------

* Basic installation: $ pip install cosmic
* Link to virtualenv tutorial
* Working with master: $ git clone && python setup.py develop

What's in an API?
-----------------

* An API is an interface, a live component in a multi-party system.
* In the context of Cosmic, an API is also a serializable object.
* In the JSON form, this object is called an API spec.
* This object stores everything necessary to interact with your data and business logic.
* Metadata: name, homepage.
* Actions: list of function definitions.
* Models: list of datatypes and definitions of how entities of those types are to be manipulated.

RPC via Actions
---------------

* Actions are API functions.
* Actions are also serialiable objects, containing the type definition of a function.
* Actions are registered with an @my_api.action() decorator.
* Remote actions are called by my_api.actions.foo().
* Accepts and returns are both optional.
* When accepts is a Struct, you can pass in values as kwargs.
* [HTTP spec]

REST via Models
---------------

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
* Authentication is done by setting and reading headers.
* On the client side, there is a hook myapi.auth_headers (set)
* On the server side, there is a hook myapi.authenticate (read)
* Authentication error should be raised when invalid credentials are provided.
* If credentials are expected but not provided, an authorization error should be raised.
* An authorization error can be raised from anywhere in the code.
* [HTTP spec]

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

