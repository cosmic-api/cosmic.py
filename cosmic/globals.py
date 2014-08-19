from contextlib import contextmanager
from UserDict import UserDict
from werkzeug.local import LocalStack


class SafeGlobal(UserDict):

    def __init__(self):
        self.stack = LocalStack()

    @property
    def data(self):
        if self.stack.top is None:
            self.stack.push({})
        return self.stack.top

    @contextmanager
    def scope(self, data):
        self.stack.push(data)
        yield
        self.stack.pop()

cosmos = SafeGlobal()



