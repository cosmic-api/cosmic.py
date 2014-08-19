from .models import BaseModel
from .types import *
from .exceptions import NotFound
from .globals import SafeGlobal


db = SafeGlobal()


class DBModel(BaseModel):
    @classmethod
    def get_by_id(cls, id):
        full_name = '{}.{}'.format(cls.api.name, cls.name)
        try:
            (id, rep) = Representation(full_name).from_json(db[cls.name][int(id)])
            return rep
        except IndexError:
            raise NotFound

    @classmethod
    def get_list(cls, **kwargs):
        full_name = '{}.{}'.format(cls.api.name, cls.name)
        if not kwargs:
            ret = []
            for row in db[cls.name]:
                ret.append(Representation(full_name).from_json(row))
            return ret
        ret = []
        for row in db[cls.name]:
            if row != None:
                keep = True
                for key, val in kwargs.items():
                    if row[key] != val:
                        keep = False
                        break
                if keep:
                    ret.append(Representation(full_name).from_json(row))
        return ret

    @classmethod
    def create(cls, **patch):
        full_name = '{}.{}'.format(cls.api.name, cls.name)
        table = db[cls.name]

        id = str(len(table))
        table.append(Representation(full_name).to_json((id, patch)))

        return id, patch

    @classmethod
    def update(cls, id, **patch):
        full_name = '{}.{}'.format(cls.api.name, cls.name)
        table = db[cls.name]
        (id, original_rep) = Representation(full_name).from_json(table[int(id)])
        original_rep.update(patch)

        table[int(id)] = Representation(full_name).to_json((id, original_rep))

        return original_rep

    @classmethod
    def delete(cls, id):
        full_name = '{}.{}'.format(cls.api.name, cls.name)

        if int(id) >= len(db[cls.name]):
            raise NotFound
        db[cls.name][int(id)] = None

