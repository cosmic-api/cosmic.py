import json
from collections import OrderedDict

from werkzeug.urls import url_decode, url_encode
from werkzeug.datastructures import MultiDict
from werkzeug.datastructures import Headers as WerkzeugHeaders

from teleport import standard_types, ParametrizedWrapper, BasicWrapper, required, optional, Box, ValidationError

def getter(name):
    from .api import API
    if name == "cosmic.API":
        return API
    elif name == "cosmic.Model":
        return Model
    elif name == "cosmic.Link":
        return Link
    elif name == "cosmic.Representation":
        return Representation
    elif name == "cosmic.Patch":
        return Patch
    else:
        raise KeyError()

globals().update(standard_types(getter))


def required_link(name, model, doc=None):
    return (name, {"model": model, "required": True, "doc": doc})

def optional_link(name, model, doc=None):
    return (name, {"model": model, "required": False, "doc": doc})



class Model(BasicWrapper):
    type_name = "cosmic.Model"
    schema = String

    @classmethod
    def assemble(cls, datum):
        from .models import M
        return M(datum)

    @classmethod
    def disassemble(cls, datum):
        return datum.type_name


class Link(ParametrizedWrapper):
    type_name = "cosmic.Link"
    param_schema = Model

    def __init__(self, param):
        self.param = param
        self.schema = Struct([
            required(u"href", String)
        ])

    def assemble(self, datum):
        url = datum['href']
        parts = url.split('/')
        if parts[-2] != self.param._name:
            raise ValidationError("Invalid url for %s link: %s" % (self.param._name, url))
        id = parts[-1]

        return self.param(id=id)

    def disassemble(self, datum):
        href = "/%s/%s" % (datum.__class__.__name__, datum.id)
        return {"href": href}


class BaseRepresentation(ParametrizedWrapper):
    param_schema = Model

    def __init__(self, param):
        self.param = model_cls = param
        self._lazy_schema = None

    @property
    def schema(self):
        if self._lazy_schema is None:

            links = [
                ("self", {
                    "required": False,
                    "schema": Link(self.param)
                })
            ]
            for name, link in self.param.links:
                required = False
                if not self.all_fields_optional:
                    required = link["required"]

                links.append((name, {
                    "required": required,
                    "schema": Link(link["model"]),
                }))

            props = [
                optional("_links", Struct(links)),
            ]
            for name, field in self.param.properties:
                required = False
                if not self.all_fields_optional:
                    required = field["required"]

                props.append((name, {
                    "required": required,
                    "schema": field['schema'],
                }))

            self._lazy_schema = Struct(props)

        return self._lazy_schema

    def assemble(self, datum):

        rep = {}
        links = datum.pop("_links", {})
        self_link = links.pop("self", None)

        rep.update(links)
        rep.update(datum)

        id = None
        if self_link is not None:
            id = self_link.id

        return (id, rep)


    def disassemble(self, datum):
        (id, rep) = datum

        links = {}
        if id:
            links["self"] = self.param(id=id)
        for name, link in OrderedDict(self.param.links).items():
            value = rep.get(name, None)
            if value != None:
                links[name] = value
        d = {}
        if links:
            d["_links"] = links
        for name in OrderedDict(self.param.properties).keys():
            value = rep.get(name, None)
            if value != None:
                d[name] = value
                
        return d

class Representation(BaseRepresentation):
    type_name = "cosmic.Representation"
    all_fields_optional = False

class Patch(BaseRepresentation):
    type_name = "cosmic.Patch"
    all_fields_optional = True



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
