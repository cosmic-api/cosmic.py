Tutorial
========

.. _tutorial-single:

Step 1: Single-function API
---------------------------

In the spirit of `Flask <http://flask.pocoo.org/>`_, let's start with something
you can copy and paste into a file, say ``words.py``:

.. code:: python

    from cosmic.api import API
    from cosmic.types import *

    words = API('words')


    @words.action(accepts=String, returns=String)
    def pluralize(word):
        if word.endswith('y'):
            return word[:-1] + 'ies'
        else:
            return word + 's'

    if __name__ == "__main__":
        words.run()

Run it:

.. code:: bash

    $ python words.py
    * Running on http://127.0.0.1:5000/

Now we can interact with the API:

.. code:: bash

    $ curl -i -X POST -H 'Content-Type: application/json' -d '"pony"' http://127.0.0.1:5000/actions/pluralize
    HTTP/1.0 200 OK
    Content-Type: application/json

    "ponies"

Did you notice the type definitions above? They help validate the data:

.. code:: bash

    $ curl -i -X POST -H 'Content-Type: application/json' -d '1' http://127.0.0.1:5000/actions/pluralize
    HTTP/1.0 400 BAD REQUEST
    Content-Type: application/json

    {"error": "Invalid String: 1"}

Step 2: Making a REST Model
---------------------------

.. seealso::

    :ref:`guide-models`

Here's a simple model:

.. code:: python

    from cosmic.models import BaseModel
    from cosmic.exceptions import NotFound

    @words.model
    class Word(BaseModel):
        methods = ['get_by_id']
        properties = [
            required(u"letters", String)
        ]
        @classmethod
        def get_by_id(cls, id):
            if id == "0":
                return {"letters": "hello"}
            else:
                raise NotFound

.. code:: bash

    $ curl -i -H 'Content-Type: application/json' http://127.0.0.1:5000/Word/0
    HTTP/1.0 200 OK
    Content-Type: application/json

    {"letters": "hello", "_links": {"self": {"href": "/Word/0"}}

.. code:: bash

    $ curl -i -H 'Content-Type: application/json' http://127.0.0.1:5000/Word/1
    HTTP/1.0 404 NOT FOUND

Step 3: Authenticating
----------------------

By default, all models and actions are accessible to all clients. To restrict
access you use authentication and authorization. Cosmic doesn't currently
support or recommend a particular method of authentication. However, it allows
you to implement your own by subclassing :class:`~cosmic.http.Server` and
:class:`~cosmic.client.APIClient`.

See :ref:`guide-authentication` for an example.
