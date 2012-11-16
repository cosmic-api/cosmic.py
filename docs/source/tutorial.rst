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
        lamas[name] = { "points": 0 }
        return True

    @lamagotchi.action
    def meditate(name):
        lamas[name]["points"] += 1
        return True

    @lamagotchi.action
    def get_state(name):
        if lamas[name]["points"] > 20:
            return "enlightened"
        else:
            return "seeking"

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
            "get_state": { "returns": {"type": "any"}, "accepts": {"type": "any"} }
        }
    }


Consuming an API
""""""""""""""""
