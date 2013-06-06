Tutorial
========

The working code for this example API can be found `here <https://github.com/cosmic-api/cosmic.py/blob/master/examples/zodiac.py>`_.

Building an API
"""""""""""""""

Start by creating a new :class:`~cosmic.api.API` object::

    import random

    from cosmic.api import API
    from cosmic.models import Model
    from teleport import *

    zodiac = API("zodiac")

To define a model, we subclass :class:`~cosmic.models.Model`.

Models are data type definitions which are helpful for validation and
generating documentation. Let's create a simple string model responsible for
the zodiac sign::

    @zodiac.model
    class Sign(Model):
        schema = String

        SIGNS = [
            "aries",
            "taurus",
            "gemini",
            "cancer",
            "leo",
            "virgo",
            "libra",
            "scorpio",
            "sagittarius",
            "capricorn",
            "aquarius",
            "pisces"
        ]

        @classmethod
        def assemble(cls, datum):
            if datum not in cls.SIGNS:
                raise ValidationError("Unknown zodiac sign", datum)
            return cls(datum)

Note the :attr:`schema` attribute in the model class. This is a Teleport
serializer, a special type definition that cosmic uses for serialization,
validation as well as to automatically generate documentation. You can get
started with Teleport `here </docs/teleport/python/>`_.

After Cosmic passes raw JSON data through the Teleport schema, it will invoke
the model's :meth:`assemble` function to perform extra validation (if you
define it) and to instantiate the model.

Now we can use this model to create an *action*, a function that may be called
with a POST request to your API::

    @zodiac.action(
        accepts=Sign,
        returns=String)
    def predict(sign):
        ret = "For %s, now is a good time to " % sign.data
        ret += random.choice([
            "build an API.",
            "mow the lawn.",
            "buy Bitcoin.",
            "get a snake tatoo."
        ])
        ret += " It is " + random.choice([
            "probable",
            "not improbable",
            "conceivable",
            "not entirely out of the question"
        ]) + " that you will meet a handsome stranger."
        return ret

The *accepts* and *returns* arguments are both schemas. Notice how we can use
the model we defined above as a Teleport schema. By providing an *accepts*
definition like the one above, we are ensuring that the function will only get
called with deserialized and validated data, in this case a :class:`Sign`
instance.

Now you are ready to run the API. The :meth:`~cosmic.api.API.run` method uses
`Flask <http://flask.pocoo.org/>`_ to serve your API::

    zodiac.run()

This will create several HTTP endpoints. If you visit ``/spec.json`` you will see:

.. code:: json

    {
        "name": "zodiac",
        "models": [
            {
                "name": "Sign",
                "schema": {"type": "string"}
            }
        ],
        "actions": {
            "map": {
                "predict": {
                    "accepts": {"type": "zodiac.Sign"},
                    "returns": {"type": "string"}
                }
            },
            "order": ["predict"]
        }
    }

This endpoint can be used to dynamically build a client for your API.
The type signatures are used for documentation and validation.

You can now interact with your new API via POST requests:

.. code:: bash

    $ curl -X POST -H "Content-Type: application/json" -d '"leo"' http://localhost:5000/actions/predict
    "For leo, now is a good time to get a snake tatoo. It is probable that you will meet a handsome stranger."

If you try to submit an invalid zodiac sign, you'll get a 400 error response:

.. code:: bash

    $ curl -X POST -H "Content-Type: application/json" -d '"tiger"' http://localhost:5000/actions/predict
    {"error": "Unknown zodiac sign: u'tiger'"}

Consuming an API
""""""""""""""""

Now that we've launched our API, we can consume it using the same library we used to build it.

.. code:: python

    >>> from cosmic.api import API
    >>> zodiac = API.load("http://localhost:5000/spec.json")
    >>> pisces = zodiac.models.Sign("pisces")
    >>> zodiac.actions.predict(pisces)
    "For pisces, now is a good time to mow the lawn. It is not entirely out of the question that you will meet a handsome stranger."

When we instantiate a model from a third-party API, the only validation Cosmic can run is schema
validation. Thus, this will work without error:

.. code:: python

    >>> pisces = zodiac.models.Sign("pies")

However, when you try to use it in an action, you will receive and error:

.. code:: python

    >>> zodiac.actions.predict(pisces)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/actions.py", line 93, in __call__
        raise InternalServerError(res.json['error'])
    werkzeug.exceptions.InternalServerError: Unknown zodiac sign: u'pies'

