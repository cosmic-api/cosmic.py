from werkzeug.local import LocalProxy, LocalStack
from flask import request

from .models import _ctx_stack, _global_cosmos


# Fixed by Armin in cbd8ec9b20405b406a8a701b34087a349b656d5d
# Will go into Werkzeug 0.8.4, remove this hack when it comes out
# http://werkzeug.pocoo.org/docs/changes/#version-0-8-4
class FixedLocalProxy(LocalProxy):
    __coerce__ = lambda x, o: x._get_current_object().__coerce__(x, o) # pragma: no cover
    __enter__ = lambda x: x._get_current_object().__enter__()
    __exit__ = lambda x, *a, **kw: x._get_current_object().__exit__(*a, **kw)

def _get_current_cosmos():
    if _ctx_stack.top != None:
        return _ctx_stack.top
    else:
        return _global_cosmos

cosmos = FixedLocalProxy(_get_current_cosmos)
