from .models import BaseModel
from .types import *
from .exceptions import NotFound
from werkzeug.local import LocalProxy, LocalStack

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


class DBModel(BaseModel):

    @classmethod
    def get_by_id(cls, id):
        try:
            (id, rep) = Representation(cls).from_json(db[cls.__name__][int(id)])
            return cls(id=id, **rep)
        except IndexError:
            raise NotFound

    @classmethod
    def get_list(cls, **kwargs):
        if not kwargs:
            ret = []
            for row in db[cls.__name__]:
                (id, rep) = Representation(cls).from_json(row)
                ret.append(cls(id=id, **rep))
            return ret
        ret = []
        for row in db[cls.__name__]:
            if row != None:
                keep = True
                for key, val in kwargs.items():
                    if row[key] != val:
                        keep = False
                        break
                if keep:
                    (id, rep) = Representation(cls).from_json(row)
                    ret.append(cls(id=id, **rep))
        return ret

    @classmethod
    def create(cls, **patch):
        table = db[cls.__name__]

        id = str(len(table))
        table.append(Representation(cls).to_json((id, patch)))

        return id, patch

    @classmethod
    def update(cls, id, **patch):
        table = db[cls.__name__]
        (id, original_rep) = Representation(cls).from_json(table[int(id)])
        original_rep.update(patch)

        table[int(id)] = Representation(cls).to_json((id, original_rep))

        return id, original_rep

    @classmethod
    def delete(cls, id):
        from .exceptions import NotFound
        if int(id) >= len(db[cls.__name__]):
            raise NotFound
        db[cls.__name__][int(id)] = None

