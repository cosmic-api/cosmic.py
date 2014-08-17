from werkzeug.local import LocalProxy

from .models import _ctx_stack, Cosmos


MODEL_METHODS = ['get_by_id', 'get_list', 'create', 'update', 'delete']

_global_cosmos = Cosmos()


def _get_current_cosmos():
    if _ctx_stack.top != None:
        return _ctx_stack.top
    else:
        return _global_cosmos


def _get_current_g():
    return _get_current_cosmos().g


cosmos = LocalProxy(_get_current_cosmos)
g = LocalProxy(_get_current_g)
