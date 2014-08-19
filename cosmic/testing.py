from .models import BaseModel
from .exceptions import NotFound
from .globals import SafeGlobal


db = SafeGlobal()


class DBModel(BaseModel):
    @classmethod
    def get_by_id(cls, id):
        try:
            return db[cls.name][id]
        except KeyError:
            raise NotFound

    @classmethod
    def get_list(cls, **kwargs):
        if not kwargs:
            return sorted(db[cls.name].items())
        ret = []
        for id, rep in db[cls.name].items():
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
        id = str(len(db[cls.name]))
        db[cls.name][id] = patch
        return id, patch

    @classmethod
    def update(cls, id, **patch):
        rep = db[cls.name][id]
        rep.update(patch)
        return rep

    @classmethod
    def delete(cls, id):
        if id not in db[cls.name]:
            raise NotFound
        del db[cls.name][id]

