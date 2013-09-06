from werkzeug.local import LocalProxy, LocalStack
from flask import request

from .models import _ctx_stack, Cosmos


_global_cosmos = Cosmos()

def _get_current_cosmos():
    if _ctx_stack.top != None:
        return _ctx_stack.top
    else:
        return _global_cosmos

cosmos = LocalProxy(_get_current_cosmos)
