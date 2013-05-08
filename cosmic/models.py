import sys
import json
import base64

from cosmic.exceptions import ValidationError, UnicodeDecodeValidationError, SpecError, JSONParseError



class Model(object):

    def __init__(self, data):
        self.data = data

    @classmethod
    def normalize(cls, datum):
        cls.validate(datum)
        return datum

    @classmethod
    def get_schema(cls):
        return cls.schema



class JSONData(Model):

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

