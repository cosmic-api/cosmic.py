from werkzeug.local import LocalProxy, LocalStack
from flask import request

from .models import _ctx_stack


def _get_current_cosmos():
    if _ctx_stack.top != None:
        return _ctx_stack.top
    else:
        raise RuntimeError("Working outside of Cosmos")

cosmos = LocalProxy(_get_current_cosmos)
