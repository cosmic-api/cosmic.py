from werkzeug.local import LocalStack, LocalProxy

__all__ = ['BaseModel', 'Cosmos', 'M']


class BaseModel(object):
    properties = []
    methods = []
    query_fields = []
    list_metadata = []
    links = []

    @classmethod
    def validate_patch(cls, datum):
        pass


class Cosmos(object):
    def __init__(self):
        self.apis = {}

    def clone(self):
        c = Cosmos()
        c.apis = dict(self.apis.items())
        return c

    def M(self, name):
        api_name, model_name = name.split('.', 1)
        return self.apis[api_name]._models[model_name]

    def __enter__(self):
        _ctx_stack.push(self)

    def __exit__(self, *args, **kwargs):
        _ctx_stack.pop()


_ctx_stack = LocalStack()


def M(name):
    from cosmic import cosmos

    return LocalProxy(lambda: cosmos.M(name))
