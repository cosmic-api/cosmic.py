Tutorial
========

Step 0: Blank API
-----------------

Before we get into the features, let's create a blank API to see how an API
is served and consumed. Here it is::

    from cosmic.api import API

    zen = API('zen')

    if __name__ == "__main__":
        zen.run()

Save this as ``zen.py`` and run:

.. code:: bash

    $ python zen.py
    * Running on http://127.0.0.1:5000/

The only endpoint provided by our API is ``/spec.json``. Let's try to GET it
to see what's inside (:mod:`json.tool` is used for pretty printing):

.. code:: bash

    $ curl http://127.0.0.1:5000/spec.json | python -m json.tool
    {
        "name": "zen",
        "actions": {
            "map": {},
            "order": []
        },
        "models": {
            "map": {},
            "order": []
        }
    }

This is the API spec, a JSON document that is used to build API clients. You
rarely need to see this spec, a mere URL is enough to load your API on a
remote computer. Open up another shell, and try the following::

    >>> from cosmic.api import API
    >>> zen = API.load("http://127.0.0.1:5000/spec.json")

Note that both on the client and the server, an API is an instance of the same
class, :class:`~cosmic.api.API`. In fact, the server and client version of
this class behave almost identically. This is one of the design goals of
Cosmic. Now that we know the workflow, let's add some functionality.

Step 1: Single-function API
---------------------------

While we encourage you to use a REST-ful approach for designing your API,
there are situationis where a simple remote procedure call is a good fit. Here
is an API that defines a single action::

    from cosmic.api import API
    from cosmic.types import Array, Integer

    mathy = API("mathy")

    @mathy.action(accepts=Array(Integer), returns=Integer)
    def add(numbers):
        return sum(numbers)

An *action* is a function exposed to the web by Cosmic. Even after applying
the :meth:`~cosmic.API.action` decorator, it remains a simple function::

    >>> from mathy import add
    >>> add([1, 2, 3])
    6

However, it also becomes accessible in the :data:`~cosmic.API.actions`
namespace of the API object::

    >>> from mathy import mathy
    >>> mathy.actions.add([1, 2, 3])
    6

Remember how the client and server components are instances of the same class?
Well, here's how you call this action from the client::

    >>> mathy = API.load("http://127.0.0.1:5000/spec.json")
    >>> mathy.actions.add([1, 2, 3])
    6

Did you notice the type definitions in the action? They help Cosmic serialize
complex data and validate it. See what happens when you pass in the wrong
type::

    >>> mathy.actions.add([1, 2, True])
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/actions.py", line 37, in __call__
        return self.endpoint(*args, **kwargs)
      File "cosmic/http.py", line 287, in __call__
        return self.api.client_hook.call(self, *args, **kwargs)
      File "cosmic/http.py", line 27, in call
        return self.parse_response(endpoint, res)
      File "cosmic/http.py", line 33, in parse_response
        return endpoint.parse_response(res)
      File "cosmic/http.py", line 347, in parse_response
        res = super(ActionEndpoint, self).parse_response(res)
      File "cosmic/http.py", line 273, in parse_response
        raise ValidationError(r['json'].datum.get('error', ''))
    teleport.ValidationError: Item at [2] Invalid Integer: True

In the background, the Cosmic client made a request, to which the Cosmic
server returned a special 400 response, which the client turned into a
:exc:`~teleport.ValidationError`. On the client side, this validation guides
in correct API usage. On the server side, it greatly reduces boilerplate and
the number potentially dangerous errors that result from malformatted data.

These type definitions can also be used to generate documentation.

The system responsible for the type definitions and serialization is a
decoupled component called Teleport.

Step 2: Defining a Custom Data Type
-----------------------------------

Teleport allows you to define custom types from scratch or in terms of other
types. These definition will aid in serialization, deserialization and
validation. With Cosmic, you can attach such definition to your API, creating
a model. Here's a simple model::

    from cosmic.models import BaseModel

    planetarium = API('planetarium')

    @planetarium.model
    class Sphere(BaseModel):
        properties = [
            required(u"name", string)
        ]

Here's how you instantiate it::

    >>> Sphere(name="Pluto")
    <examples.planetarium.Sphere object at 0xa8b434c>

And on the server::

    >>> planetarium.models.Sphere(name="Neptune")
    <cosmic.api.Sphere object at 0xa8076ec>

Actions can take models as parameters::

    @planetarium.action(accepts=Sphere, returns=String)
    def hello(sphere):
        return "Hello, %s" % sphere.name

Now you can call this both from the client or from the server::

    >>> neptune = planetarium.models.Sphere(name="Neptune")
    >>> planetarium.actions.hello(neptune)
    u'Hello Neptune'

Step 3: RESTful API
-------------------

Some models not only represent data types, but also correspond to sets of
real-world objects. Commonly the model will correspond with a database table
and the object with a row in that table. Cosmic doesn't care where these
objects are stored, you are expected to provide access to them by implementing
up to 5 methods.

Let's augment the model we defined above to allow Cosmic to expose it::

    @planetarium.model
    class Sphere(BaseModel):
        properties = [
            required("name", String)
        ]

        @classmethod
        def get_by_id(cls, id):
            if id in spheres:
                return spheres[id]
            else:
                return None

    spheres = {
        "0": Sphere(name="Earth", id="0"),
        "1": Sphere(name="Moon", id="0")
    }

Every method implemented on the server becomes accessible on the client::

    >>> planetarium = API.load('http://localhost:5000/spec.json')
    >>> sphere = planetarium.models.Sphere.get_by_id("0")
    >>> sphere
    <cosmic.api.Sphere object at 0xa8076ec>
    >>> sphere.name
    u'Earth'

Step 4: Authenticating
----------------------

By default, all models and actions are accessible to all clients. To restrict
access you use authentication and authorization. Cosmic doesn't currently
support or recommend a particular method of authentication. However, it allows
you to implement your own via :data:`~cosmic.api.API.client_hook` and 
:data:`~cosmic.api.API.server_hook`.

See :ref:`guide-authentication` for an example.
