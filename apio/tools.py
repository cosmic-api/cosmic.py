import inspect
from apio.exceptions import SpecError

def get_arg_spec(func):
    """ Calculate JSON schema spec for action.
    If function has no arguments, returns None.
    """
    # Based on the passed in function's arguments, there are
    # three choices:
    args, varargs, keywords, defaults = inspect.getargspec(func)
    if varargs or keywords:
        raise SpecError("Cannot define action with splats (* or **)")
    # No arguments: accepts null
    if len(args) == 0:
        return None
    # One argument: accepts a single JSON object
    if len(args) == 1:
        return { "type": "any" }
    # Multiple arguments: accepts a JSON object with a property for
    # each argument, each property being of type 'any'
    spec = {
        "type": "object",
        "properties": {}
    }
    # Number of non-keyword arguments (required ones)
    numargs = len(args)
    if defaults:
        numargs -= len(defaults)
    for i, arg in enumerate(args):
        if i < numargs:
            s = { "type": "any", "required": True }
        else:
            s = { "type": "any" }
        spec["properties"][arg] = s
    return spec
        
