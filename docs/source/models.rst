Model System
============

APIO ships with a simple JSON-based schema and model system.

JSON schema
-----------

We provide with a simple way to define the format of your data with a schema written in JSON.

.. note::

    *Why invent our own JSON schema system?*
    
    Before deciding to go with our own system, we took a good look at some existing options. Our best candidates were `JSON Schema <http://json-schema.org/>`_ and `Apache Avro <http://avro.apache.org/>`_. JSON Schema has a significant flaw: the order of object attributes is not preserved. Apache Avro had a different problem: because an attribute can be defined as allowing multiple types, objects needed to be wrapped in an annotation layer to avoid ambiguity. Instead of ``{"name": "Jenn"}`` we would have to output ``{"Person": {"name": "Jenn"}}``. In the context of REST APIs, this is uncommon and weird.

    Because APIO must be extremely portable, it is essential that we keep the feature list to a reasonable minimum. In this instance, the minimum is generating documentation and basic validation of data structure and types. Instead of making you learn a new `DSL <http://en.wikipedia.org/wiki/Domain-specific_language>`_ for obscure validation, we encourage you to use the power of your language. The benefits of describing schemas in minute detail are greatly outweighed by the costs of growing the amount of code that needs to be ported.
