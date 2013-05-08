import json

from cosmic.exceptions import ValidationError


class JSONData(object):

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        contents = json.dumps(self.data)
        if len(contents) > 60:
            contents = contents[:56] + " ..."
        return "<JSONData %s>" % contents

    @classmethod
    def from_string(cls, s):
        if s == "":
            return None
        # No need to validate:
        return cls.normalize(json.loads(s))

    @classmethod
    def normalize(cls, datum):
        return cls(datum)

    def serialize(self):
        return self.data

    @classmethod
    def to_string(cls, s):
        if s == None:
            return ""
        return json.dumps(s.serialize())



def normalize_json(schema, datum):
    if schema and not datum:
        raise ValidationError("Expected JSONData, found None")
    if datum and not schema:
        raise ValidationError("Expected None, found JSONData")
    if schema and datum:
        return schema.deserialize(datum.data)
    return None

def serialize_json(schema, datum):
    if schema and not datum:
        raise ValidationError("Expected data, found None")
    if datum and not schema:
        raise ValidationError("Expected None, found data")
    if schema and datum:
        return JSONData(schema.serialize(datum))
    return None

