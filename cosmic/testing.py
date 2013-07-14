from .models import Model
from werkzeug.local import LocalProxy, LocalStack
from flask import request

_db_ctx_stack = LocalStack()

db = LocalProxy(lambda: _db_ctx_stack.top)

class DBContext(object):

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        _db_ctx_stack.push(self.db)
        return self.db

    def __exit__(self, *args, **kwargs):
        _db_ctx_stack.pop()


class DBModel(Model):

    @classmethod
    def get_by_id(cls, id):
        try:
            return cls.from_json(db[cls.db_table][int(id)])
        except IndexError:
            return None

    @classmethod
    def get_list(cls, **kwargs):
        if not kwargs:
            return map(cls.from_json, db[cls.db_table])
        ret = []
        for row in db[cls.db_table]:
            if row != None:
                keep = True
                for key, val in kwargs.items():
                    if row[key] != val:
                        keep = False
                        break
                if keep:
                    ret.append(cls.from_json(row))
        return ret

    def save(self):
        db[self.__class__.db_table][int(self.id)] = self.__class__.to_json(self)

    def delete(self):
        db[self.__class__.db_table][int(self.id)] = None

