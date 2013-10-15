Tutorial
========

Step 0: Null API
----------------

* Before we get into the features, let's see what exactly is a Cosmic API.
* Here's the null API:
* [code]
* Now let's run the server:
* [code]
* Now let's fetch the spec that remote instances of Cosmic will use to build clients:
* [code]
* On another computer, you may load an API by doing this:
* [code]
* This is just a serialized and deserialized version of the original API object.
* You can serialize it again by calling API.to_json:
* [code]

Step 1: Single-function API
---------------------------

* Now let's make it useful by adding an action:
* [code]
* An action is just a function exposed to the web by Cosmic.
* See how your API spec is now different:
* [code]
* A remote API may call it like this:
* [code]
* Notice the type definitions.
* They help Cosmic serialize complex data and validate it.
* Here's what happens when you pass in the wrong type from a remote API:
* [code]
* The call never actually reached your function.
* For dynamically-typed languages like Python this improves security.
* This also helps generate documentation.
* The system responsible for the type definitions and serialization is a decoupled component called Teleport.

Step 2: Defining a Custom Data Type
-----------------------------------

* Teleport allows you to define custom types from scratch or in terms of primitive types.
* The definition will aid in serialization, deserialization and validation.
* Better yet, define them in terms of types supplied by Teleport.
* This will help you automatically generate documentation:
* [docs]
* And spare you the boilerplate serialization code.
* With Cosmic, you can attach such definition to your API, creating a model.
* Here's a simple model:
* [code]
* Here's how you instantiate it:
* [code]
* You can turn your existing classes into models if you give them the JSON type and implement assemble, disassemble.

Step 3: RESTful API
-------------------

* Some models not only represent data types, but also correspond to a set of real-world objects.
* Commonly the model will correspond with a database table and the object with a row in that table.
* Cosmic doesn't care where these objects are stored so long as you implement 5 methods [link to overview]
* Let's augment the model we defined above to allow Cosmic to expose it:
* [code]
* Now if you load this API from a remote computer, you can use these methods to access the objects:
* [code]

Step 4: Authenticating
----------------------

* By default, all models and actions are accessible to all clients.
* To restrict access you use authentication and authorization.
* Cosmic doesn't currently support or recommend a particular method of authentication.
* However, it allows you to implement your own via api.client_hook and api.server_hook
* These hooks let you control HTTP message processing.
* First, let's teach the server to ask for authentication with WWW-Authenticate
* [code]
* Now, let's let the client provide it:
* [code]
* Then, let's teach the server to check for it:
* [code]
* Sometimes (OAuth), a request might get an unexpected 401 response.
* In these cases, you may want to get new credentials, then retry the request:
* [code]
