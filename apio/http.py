import json

from flask import request, make_response

from apio.exceptions import *
from apio.tools import JSONPayload, normalize


def corsify_view(allowed_methods):
    """Takes a Flask view function and augments it with CORS
    functionality. Implementation based on this tutorial:
    http://www.html5rocks.com/en/tutorials/cors/

    Access-Control-Allow-Credentials can be emulated, so there's no
    real reason to support it. IE doesn't support wildcard
    Access-Control-Allow-Origin so we just echo the request Origin
    instead. See here for notes:
    https://github.com/alexandru/crossdomain-requests-js/wiki/Troubleshooting

    Note that many CORS implementations are broken. For example,
    see: http://stackoverflow.com/q/12780839/212584
    """
    def decorator(view_func):
        def corsified(*args, **kwargs):
            """Flask view for handling the CORS preflight request
            """
            origin = request.headers.get("Origin", None)
            # Preflight request
            if request.method == "OPTIONS":
                # No Origin?
                if origin == None:
                    error = "Preflight CORS request must include Origin header"
                    return error, 400
                # Access-Control-Request-Method is not set or set
                # wrongly?
                requested_method = request.headers.get("Access-Control-Request-Method", None)
                if requested_method not in allowed_methods:
                    error = "Access-Control-Request-Method header must be set to "
                    error += " or ".join(allowed_methods)
                    return error, 400
                # Everything is good, make response
                res = make_response("", 200)
                res.headers["Access-Control-Allow-Origin"] = origin
                res.headers["Access-Control-Allow-Methods"] = ",".join(allowed_methods)
                # Allow all requested headers
                headers = request.headers.get('Access-Control-Request-Headers', None)
                if headers != None:
                    res.headers["Access-Control-Allow-Headers"] = headers
            # Actual request
            else:
                # If view_func returns a tuple, make_response will
                # turn it into flask.Response. If it already returns a
                # Response, make_response will do nothing
                res = make_response(view_func(*args, **kwargs))
                if origin != None:
                    res.headers["Access-Control-Allow-Origin"] = origin
            return res
        return corsified
    return decorator

def apio_view(debug=False, accepts=None, returns=None):
    """Wraps the function with some generic error handling
    """
    def wrapper(view_func):
        def wrapped():
            # Make sure Content-Type is right
            ct = request.headers.get('Content-Type', None)
            if ct != "application/json":
                return json.dumps({
                    "error": 'Content-Type must be "application/json"'
                }), 400
            # Make sure JSON is valid
            try:
                payload = JSONPayload.from_string(request.data)
            except ValueError:
                return json.dumps({
                    "error": "Invalid JSON"
                }), 400
            # If function takes no arguments, request must be empty
            if accepts == None and payload:
                return json.dumps({
                    "error": "Request content must be empty"
                }), 400
            # If function takes arguments, request cannot be empty
            if accepts != None and not payload:
                return json.dumps({
                    "error": "Request content cannot be empty"
                }), 400
            # Validate incoming data
            if payload:
                try:
                    normalized = normalize(accepts, payload.json)
                    payload = JSONPayload(normalized)
                except ValidationError:
                    return json.dumps({
                        "error": "Validation failed" + json.dumps(accepts)
                    }), 400
            # Try running the actual function
            try:
                data = view_func(payload=payload)
                # May raise ValidationError, will be caught below (500 error)
                if returns:
                    data = normalize(returns, data)
                    return json.dumps(data)
                else:
                    return ""
            except APIError as err:
                return json.dumps({
                    "error": err.args[0]
                }), err.http_code
            except AuthenticationError:
                return json.dumps({
                    "error": "Authentication failed"
                }), 401
            # Any other exception should be handled gracefully
            except Exception as e:
                if debug: raise e
                return json.dumps({
                    "error": "Internal Server Error"
                }), 500
        return wrapped
    return wrapper
