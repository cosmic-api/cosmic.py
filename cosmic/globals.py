from contextlib import contextmanager
from UserDict import UserDict
from werkzeug.local import LocalStack


class SafeGlobal(UserDict):

    def __init__(self):
        self.stack = LocalStack()
        self.stack.push({})

    @property
    def data(self):
        return self.stack.top

    @contextmanager
    def scope(self, data):
        self.stack.push(data)
        yield
        self.stack.pop()


cosmos = SafeGlobal()



