import inspect
from apio.exceptions import SpecError

def get_arg_spec(func):
    """Calculate JSON schema spec for action.
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
        
def apply_to_action_func(func, *obj_or_nothing):
    """Applies a JSON object to the user-defined action function
    based on its argument spec. The second parameter can be None
    to mean an explicit null value or it can be omitted to let the
    function use its default.
    """
    args, varargs, keywords, defaults = inspect.getargspec(func)
    if len(args) == 0:
        if obj_or_nothing:
            raise SpecError("%s takes no arguments" % func.__name__)
        return func()
    if len(args) == 1:
        # We weren't passed a value
        if not obj_or_nothing:
            # Function does not have defaults but we weren't passed a value
            if not defaults:
                raise SpecError("%s takes one argument" % func.__name__)
            # We weren't passed a value, but there's a default
            return func()
        # We were passed a value, safe to apply regardless of defaults
        return func(obj_or_nothing[0])
    # func takes multiple arguments, make sure we have something to work with..
    if not obj_or_nothing or type(obj_or_nothing[0]) is not dict:
        raise SpecError("%s expects an object" % func.__name__)
    obj = obj_or_nothing[0]
    # Number of non-keyword arguments (required ones)
    numargs = len(args)
    if defaults:
        numargs -= len(defaults)
    apply_args = []
    apply_kwargs = {}
    for i, arg in enumerate(args):
        # args
        if i < numargs:
            if arg not in obj.keys():
                raise SpecError("%s is a required argument" % arg)
            apply_args.append(obj.pop(arg))
        # kwargs
        elif arg in obj.keys():
            apply_kwargs[arg] = obj.pop(arg)
    # Some stuff still remaining in the object?
    if obj:
        raise SpecError("Unknown arguments: %s" % ", ".join(obj.keys()))
    return func(*apply_args, **apply_kwargs)

