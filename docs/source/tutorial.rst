Tutorial
========

Building an API
"""""""""""""""

Start by creating a new API object. Specify a unique name, and a root URL for the new API::

    from apio import API, APIError
    lamagotchi = API("lamagotchi", "http://lamagotchi.herokuapp.com")

Now we can define actions::

    lamas = {}

    @lamagotchi.action
    def create(name):
        lamas[name] = 0
        return True

    @lamagotchi.action
    def meditate(name):
        lamas[name] += 1
        return True

    @lamagotchi.action
    def state(name):
        if lamas[name] > 5000:
            return "enlightened"
        else:
            return "seeking"

    @lamagotchi.action
    def highscores():
        return sorted(lamas.items(), key=lambda lama: lama[1])

The last remaining step is to run the API::

    lamagotchi.run()

This will create several HTTP endpoints. If you visit ``/spec.json`` you will see:

.. code:: json

    {
        "url": "http://lamagotchi.herokuapp.com",
        "name": "lamagotchi",
        "actions": {
            "create": { "returns": {"type": "any"}, "accepts": {"type": "any"} },
            "meditate": { "returns": {"type": "any"}, "accepts": {"type": "any"} },
            "state": { "returns": {"type": "any"}, "accepts": {"type": "any"} },
            "highscores": { "returns": {"type": "any"}, "accepts": {"type": "null"} }
        }
    }

This endpoint is used to build a client for your API.
The type signatures so far just indicate whether your action takes an argument or not, but in the future they will be derived from type annotations and used for automatic documentation and validation.

You can now interact with your new API via POST requests:

.. code:: bash

    $ curl -X POST -H "Content-Type: application/json" -d '"steve"' http://localhost:5000/actions/create
    {"data": true}
    $ curl -X POST -H "Content-Type: application/json" -d '"steve"' http://localhost:5000/actions/state
    {"data": "seeking"}

What if we try a lama that doesn't exist yet?

.. code:: bash

    $ curl -X POST -H "Content-Type: application/json" -d '"joe"' http://localhost:5000/actions/state
    {"error": "Internal Server Error"}

This caused a ``KeyError`` which was caught by apio and presented as a generic 500 response.
If you'd like to see a custom error message, you can raise an ``apio.APIError`` in your action function.

.. code:: python

    @lamagotchi.action
    def state(name):
        if name not in lamas.keys():
            raise apio.APIError("Lama Not Found")
        if lamas[name] > 5000:
            return "enlightened"
        else:
            return "seeking"

.. code:: bash

    $ curl -X POST -H "Content-Type: application/json" -d '"joe"' http://localhost:5000/actions/state
    {"error": "Lama Not Found"}

Consuming an API
""""""""""""""""

Now that we've launched our API on Heroku (see `this page <https://devcenter.heroku.com/articles/python>`_ for instructions), we can consume it using the same library we used to build it.

.. code:: python

    >>> from apio import API
    >>> lamagotchi = API.load("http://lamagotchi.herokuapp.com/spec.json")
    >>> steve = lamagotchi.call("create", "steve")
    >>> lamagotchi.call("state", "steve")
    u'seeking'
    >>> lamagotchi.call("meditate", "steve")
    u'True'
