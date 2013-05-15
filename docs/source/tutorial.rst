Tutorial
========

The working code for this example API can be found `here <https://github.com/cosmic-api/horoscope-tutorial.py>`_.

Building an API
"""""""""""""""

Start by creating a new API object::

    import random

    from cosmic.api import API
    from cosmic.exceptions import ValidationError

    horoscope = API("horoscope")

To define a model, we subclass :class:`~cosmic.models.Model` or
:class:`~cosmic.models.ClassModel` and attach it to our API via a decorator.

Models are data type definitions which are helpful for validation and
generating documentation. For data types consisting of a single primitive
value, such as a string, you should subclass :class:`~cosmic.models.Model`.
For data types that have keys and values, you should subclass
:class:`~cosmic.models.ClassModel`. Read more about it in :ref:`key-value-models`.
For now, let's create a simple string model responsible for the
zodiac sign::

    @horoscope.model
    class Sign(Model):
        schema = normalize_schema({"type": "string"})

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
        def validate(cls, datum):
            if datum not in cls.SIGNS:
                raise ValidationError("Unknown zodiac sign", datum)

Now we can use this model to create an *action*, a function that may be called
with a POST request to your API::

    @horoscope.action(
        accepts=normalize_schema({"type": "horoscope.Sign"}),
        returns=normalize_schema({"type": "string"}))
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

Now you are ready to run the API. The :meth:`~cosmic.api.API.run` method uses
`Flask <http://flask.pocoo.org/>`_ to serve your API::

    horoscope.run()

This will create several HTTP endpoints. If you visit ``/spec.json`` you will see:

.. code:: json

    {
        "name": "horoscope",
        "models": [
            {
                "name": "Sign",
                "schema": {"type": "string"}
            }
        ],
        "actions": [
            {
                "name": "predict",
                "accepts": {"type": "horoscope.Sign"},
                "returns": {"type": "string"}
            }
        ]
    }

This endpoint can be used to dynamically build a client for your API.
The type signatures are used for documentation and validation.

You can now interact with your new API via POST requests:

.. code:: bash

    $ curl -X POST -H "Content-Type: application/json" -d '"leo"' http://localhost:5000/actions/create
    "For leo, now is a good time to get a snake tatoo. It is probable that you will meet a handsome stranger."

If you try to submit an invalid zodiac sign, you'll get a 400 error response:

.. code:: bash

    $ curl -X POST -H "Content-Type: application/json" -d '"tiger"' http://localhost:5000/actions/predict
    {"error": "Unknown zodiac sign: \"tiger\""}

Consuming an API
""""""""""""""""

Now that we've launched our API, we can consume it using the same library we used to build it.

.. code:: python

    >>> from cosmic.api import API
    >>> horoscope = API.load("http://localhost:5000/spec.json")
    >>> pisces = horoscope.models.Sign("pisces")
    >>> horoscope.predict(pisces)
    "For pisces, now is a good time to mow the lawn. It is not entirely out of the question that you will meet a handsome stranger."

When we instantiate a model from a third-party API, the only validation Cosmic can run is schema
validation. Thus, this will work without error:

.. code:: python

    >>> pisces = horoscope.models.Sign("pies")

However, when you try to use it in an action, you will receive and error:

.. code:: python

    >>> horoscope.actions.predict(pisces)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "cosmic/actions.py", line 93, in __call__
        raise APIError(res.json['error'])
    cosmic.exceptions.APIError: Unknown zodiac sign: "pies"

