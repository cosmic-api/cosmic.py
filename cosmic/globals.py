from contextlib import contextmanager
from UserDict import UserDict
from werkzeug.local import get_ident

__all__ = ['thread_local', 'SwappableDict', 'ThreadLocalDict']

storage = {}


@contextmanager
def thread_local():
    ident = get_ident()
    storage[ident] = local = {}
    yield local
    del storage[ident]


class SwappableDict(UserDict):

    @contextmanager
    def swap(self, new):
        old = self.data
        self.data = new
        yield
        self.data = old


class ThreadLocalDict(SwappableDict):

    def __init__(self):
        pass

    @property
    def data(self):
        return storage[get_ident()].setdefault(id(self), {})


cosmos = SwappableDict()
