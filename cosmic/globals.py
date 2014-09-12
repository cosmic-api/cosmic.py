from contextlib import contextmanager
from collections import MutableMapping
from werkzeug.local import get_ident

from cosmic.exceptions import ThreadLocalMissing

__all__ = ['thread_local', 'SwappableDict', 'ThreadLocalDict']

storage = {}


@contextmanager
def thread_local():
    """A context manager for safely creating and deleting the thread-local
    necessary for :class:`~cosmic.globals.ThreadLocalDict`.

    .. code::

        g = ThreadLocalDict()

        with thread_local():
            # g is only accessible within this context
            g['foo'] = 1

    """
    ident = get_ident()
    storage[ident] = local = {}
    yield local
    del storage[ident]


@contextmanager
def ensure_thread_local():
    if get_ident() in storage:
        yield
    else:
        with thread_local():
            yield


def thread_local_middleware(app):
    """To put your entire application in a :func:`~cosmic.globals.thread_local`
    context, you must put it at the entry point of your application's thread.
    In the case of a threading WSGI server, this is achieved by wrapping your
    WSGI application in this middleware.

    Note that just like the rest of this module, this middleware isn't tied to
    Cosmic in any way. For example, you can use it to enable a
    :class:`~cosmic.globals.ThreadLocalDict` inside a Django application:

    .. code::

        from django.core.wsgi import get_wsgi_application
        from cosmic.globals import thread_local_middleware

        application = thread_local_middleware(get_wsgi_application())

    .. seealso::
        `How to deploy Django with WSGI
        <https://docs.djangoproject.com/en/dev/howto/deployment/wsgi/>`_

    :param app: WSGI application
    :return: WSGI application
    """
    def application(environ, start_response):
        with thread_local():
            return app(environ, start_response)
    return application


class SwappableDict(MutableMapping):

    def __init__(self, data=None):
        if data is None:
            self.data = {}
        else:
            self.data = data

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, val):
        self.data[key] = val

    def __delitem__(self, key):
        del self.data[key]

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return self.data.__iter__()

    def keys(self):
        return self.data.keys()

    def __repr__(self):
        return repr(self.data)

    @contextmanager
    def swap(self, new):
        old = self.data
        self.data = new
        yield
        self.data = old


class ThreadLocalDict(SwappableDict):
    """A dictionary-like object that stores its values inside a thread-local.
    Useful for storing global state safely. Instantiate this once and import
    it everywhere to read and write global values (e.g. the currently
    authenticated user or database connections).
    """

    def __init__(self):
        pass

    def __repr__(self):
        if get_ident() in storage:
            return repr(self.data)
        else:
            return '<unbound ThreadLocalDict>'

    @property
    def data(self):
        try:
            local = storage[get_ident()]
        except KeyError:
            raise ThreadLocalMissing()
        return local.setdefault(id(self), {})


cosmos = SwappableDict()
