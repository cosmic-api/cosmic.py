from contextlib import contextmanager
from UserDict import UserDict
from werkzeug.local import LocalStack


class SafeGlobal(UserDict):

    def __init__(self, thread_local=True):
        if thread_local:
            self.stack = LocalStack()
        else:
            self.stack = GlobalStack()

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


class GlobalStack(object):

    def __init__(self):
        self.data = []

    def push(self, item):
        self.data.append(item)

    def pop(self):
        self.data.pop()

    @property
    def top(self):
        if self.data:
            return self.data[-1]
        return None


cosmos = SafeGlobal(thread_local=False)



