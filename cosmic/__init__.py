from werkzeug.local import LocalProxy, LocalStack
from .models import _ctx_stack
from .http import _request_ctx_stack


# Fixed by Armin in cbd8ec9b20405b406a8a701b34087a349b656d5d
# Will go into Werkzeug 0.8.4, remove this hack when it comes out
# http://werkzeug.pocoo.org/docs/changes/#version-0-8-4
class FixedLocalProxy(LocalProxy):
    __coerce__ = lambda x, o: x._get_current_object().__coerce__(x, o) # pragma: no cover
    __enter__ = lambda x: x._get_current_object().__enter__()
    __exit__ = lambda x, *a, **kw: x._get_current_object().__exit__(*a, **kw)

cosmos = FixedLocalProxy(lambda: _ctx_stack.top)
request = FixedLocalProxy(lambda: _request_ctx_stack.top)


