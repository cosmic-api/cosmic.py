from teleport import standard_types, required, optional, Box, ValidationError

def getter(name):
    from .api import API
    from .actions import Function
    from .models import M
    if name == "cosmic.API":
        return API
    elif name == "cosmic.Function":
        return Function
    elif '.' in name:
        return M(name)
    raise KeyError()

globals().update(standard_types(getter))