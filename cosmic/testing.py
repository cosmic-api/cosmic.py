from multiprocessing import Process
from contextlib import contextmanager

from .models import BaseModel
from .exceptions import NotFound
from .globals import SwappableDict, cosmos


db = SwappableDict()


class DBModel(BaseModel):
    @classmethod
    def get_by_id(cls, id):
        try:
            return db[cls.table_name][id]
        except KeyError:
            raise NotFound

    @classmethod
    def get_list(cls, **kwargs):
        if not kwargs:
            return sorted(db[cls.table_name].items())
        ret = []
        for id, rep in db[cls.table_name].items():
            keep = True
            for key, val in kwargs.items():
                if rep[key] != val:
                    keep = False
                    break
            if keep:
                ret.append((id, rep))
        return sorted(ret)

    @classmethod
    def create(cls, **patch):
        id = str(len(db[cls.table_name]))
        db[cls.table_name][id] = patch
        return id, patch

    @classmethod
    def update(cls, id, **patch):
        rep = db[cls.table_name][id]
        rep.update(patch)
        return rep

    @classmethod
    def delete(cls, id):
        if id not in db[cls.table_name]:
            raise NotFound
        del db[cls.table_name][id]


@contextmanager
def served_api(api, port, **kwargs):
    from time import sleep

    p = Process(target=api.run, args=(port,), kwargs=kwargs)
    p.start()
    sleep(0.1)

    try:
        with cosmos.swap({}):
            yield
    except Exception as e:
        raise e
    finally:
        p.terminate()


class WildcardClass(object):
    def __eq__(self, other):
        return True

Wildcard = WildcardClass()

