import json
from collections import OrderedDict

from werkzeug.urls import url_decode, url_encode
from werkzeug.datastructures import MultiDict
from werkzeug.datastructures import Headers as WerkzeugHeaders

from teleport import standard_types, ParametrizedWrapper, BasicWrapper, required, optional, Box, ValidationError

def getter(name):
    from .api import API
    from .actions import Action
    from .models import M
    if name == "cosmic.API":
        return API
    elif name == "cosmic.Action":
        return Action
    elif name == "cosmic.Model":
        return Model
    elif '.' in name:
        return M(name)
    raise KeyError()

globals().update(standard_types(getter))


class URLParams(ParametrizedWrapper):
    """A Teleport type that behaves mostly like the :class:`Struct`
    type, except it serializes the data into a query string::

        >>> p = URLParams([
        ...     required("foo", Boolean),
        ...     required("bar", Integer)
        ... ])
        ...
        >>> p.to_json({"foo": True, "bar": 3})
        'foo=true&bar=3'
        >>> p.from_json("foo=false&bar=0")
        {'foo': False, 'bar': 0}

    A string parameter or a parameter whose type is a wrapper over string will
    not require quotes:

        >>> from cosmic.types import DateTime
        >>> schema = URLParams([
        ...     required('birthday', DateTime)
        ... ])
        >>> schema.from_json('birthday=1991-08-12T00%3A00%3A00')
        {'birthday': datetime.datetime(1991, 8, 12, 0, 0)}

    """
    schema = String

    def __init__(self, param):
        if type(param) == list:
            param = OrderedDict(param)
        self.param = param

    def assemble(self, datum):
        # Use Werkzeug to turn URL params into a dict
        return self.from_multi_dict(url_decode(datum))

    def disassemble(self, datum):
        return url_encode(self.to_multi_dict(datum))

    def from_multi_dict(self, md):
        from .tools import is_string_type
        # Where only a single param was
        md = md.to_dict(flat=False)
        ret = {}
        for name, field in self.param.items():
            if name in md.keys():
                if len(md[name]) > 1:
                    raise ValidationError("Repeating query parameters not allowed: %s" % name)
                if is_string_type(field['schema']):
                    ret[name] = md[name][0]
                else:
                    ret[name] = json.loads(md[name][0])
        return Struct(self.param).from_json(ret)

    def to_multi_dict(self, datum):
        from .tools import is_string_type
        d = Struct(self.param).to_json(datum)
        md = MultiDict()
        for name, field in self.param.items():
            if name in d.keys():
                if is_string_type(field['schema']):
                    md[name] = d[name]
                else:
                    md[name] = json.dumps(d[name])
        return md



class Headers(BasicWrapper):
    schema = Array(Struct([
        required("name", String),
        required("value", String),
    ]))

    @classmethod
    def assemble(cls, datum):
        headers = WerkzeugHeaders()
        for header in datum:
            headers.add(header["name"], header["value"])
        return headers

    @classmethod
    def disassemble(cls, datum):
        headers = []
        for name, value in datum.items():
            headers.append({
                "name": name,
                "value": value
            })
        return headers



class Model(BasicWrapper):
    schema = Struct([
        optional("data_schema", Schema),
        required("links", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ]))),
        required("query_fields", OrderedMap(Struct([
            required(u"schema", Schema),
            required(u"required", Boolean),
            optional(u"doc", String)
        ])))
    ])



