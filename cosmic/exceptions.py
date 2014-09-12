from __future__ import unicode_literals


class Either(object):
    def __init__(self, exception=None, value=None):
        if exception is not None and value is not None:
            raise RuntimeError("Impossible Either")
        self.exception = exception
        self.value = value


class SpecError(Exception):
    pass


class NotFound(Exception):
    """Expected to be raised by :meth:`get_by_id`, :meth:`update` and
    :meth:`delete` when the resource is not found. Cosmic will convert
    it to a 404 response on the server, and on the client, it will
    interpret this response by reraising the exception.
    """
    pass


class HTTPError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(HTTPError, self).__init__(code, message)


class RemoteHTTPError(HTTPError):
    pass


class ThreadLocalMissing(Exception):
    """Raised when trying to access a value inside
    :class:`cosmic.globals.ThreadLocalDict` without creating a thread-local
    to store it on. See :func:`cosmic.globals.thread_local` and
    :func:`cosmic.globals.thread_local_middleware`.
    """
    pass
