import json
from collections import OrderedDict

from werkzeug.urls import url_decode, url_encode
from werkzeug.datastructures import MultiDict
from werkzeug.datastructures import Headers as WerkzeugHeaders
from teleport import standard_types, ParametrizedWrapper, BasicWrapper, \
    required, optional, Box, ValidationError

from .globals import cosmos

__all__ = ['Integer', 'Float', 'Boolean', 'String', 'Binary', 'DateTime',
           'JSON', 'Array', 'Map', 'OrderedMap', 'Struct', 'Schema', 'Model',
           'Link', 'Representation', 'Patch', 'APISpec', 'URLParams',
           'Headers', 'Box', 'required', 'optional', 'required_link',
           'optional_link', 'ValidationError']


def getter(name):
    if name == "cosmic.APISpec":
        return APISpec
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

# Explicit definitions for static analyzers
Integer = None
Float = None
Boolean = None
String = None
Binary = None
DateTime = None
JSON = None
Array = None
Map = None
OrderedMap = None
Struct = None
Schema = None
globals().update(standard_types(getter))


def required_link(name, model, doc=None):
    return name, {"model": model, "required": True, "doc": doc}


def optional_link(name, model, doc=None):
    return name, {"model": model, "required": False, "doc": doc}


class Model(BasicWrapper):
    """A Teleport type representing an API model. Its JSON form is
    a dotted string, the native form is the same string.
    """
    type_name = "cosmic.Model"
    schema = String

    @classmethod
    def assemble(cls, datum):
        return datum

    @classmethod
    def disassemble(cls, datum):
        return datum


class Link(ParametrizedWrapper):
    """A Teleport type representing a link to an object. Its native form is
    simply a resource id. It takes a :class:`~cosmic.types.Model` as
    parameter:

    .. code:: python

        >>> Link(places.models.City).to_json("3")
        {"href": "/City/3"}
        >>> Link(places.models.City).from_json({"href": "/City/3"})
        "3"

    """
    type_name = "cosmic.Link"
    param_schema = Model

    def __init__(self, param):
        self.param = param
        self.api_name, self.model_name = param.split('.', 1)
        self.schema = Struct([
            required(u"href", String)
        ])

    def assemble(self, datum):
        url = datum['href']
        parts = url.split('/')
        if parts[-2] != self.model_name:
            raise ValidationError("Invalid url for %s link: %s" % (self.model_name, url))
        return parts[-1]

    def disassemble(self, datum):
        href = "/%s/%s" % (self.model_name, datum)
        return {"href": href}


class BaseRepresentation(ParametrizedWrapper):
    param_schema = Model

    def __init__(self, param):
        self.param = param
        self.api_name, self.model_name = self.param.split('.', 1)
        self._lazy_schema = None

    @property
    def model_spec(self):
        return cosmos[self.api_name].spec['models'][self.model_name]

    @property
    def schema(self):
        if self._lazy_schema is None:

            links = [
                ("self", {
                    "required": False,
                    "schema": Link(self.param)
                })
            ]
            for name, link in self.model_spec['links'].items():
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
            for name, field in self.model_spec['properties'].items():
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
        self_id = links.pop("self", None)

        rep.update(links)
        rep.update(datum)

        return (self_id, rep)


    def disassemble(self, datum):
        (id, rep) = datum

        links = {}
        if id:
            links["self"] = id
        for name, link in self.model_spec['links'].items():
            value = rep.get(name, None)
            if value != None:
                links[name] = value
        d = {}
        if links:
            d["_links"] = links
        for name in self.model_spec['properties'].keys():
            value = rep.get(name, None)
            if value != None:
                d[name] = value

        return d


class Representation(BaseRepresentation):
    """A Teleport type representing a model representation. Its native form is
    a dict as defined by :data:`~cosmic.models.BaseModel.properties` and
    :data:`~cosmic.models.BaseModel.links`. Links are represented by plain
    string ids.

    It takes a :class:`~cosmic.types.Model` as  parameter.
    """
    type_name = "cosmic.Representation"
    all_fields_optional = False


class Patch(BaseRepresentation):
    """A Teleport type representing a model patch. Its native form is similar
    to that of :class:`~cosmic.types.Representation`, except all fields are
    optional. To make a field required, use
    :meth:`~cosmic.models.BaseModel.validate_patch`.

    It takes a :class:`~cosmic.types.Model` as  parameter.
    """
    type_name = "cosmic.Patch"
    all_fields_optional = True

    def assemble(self, datum):
        self_id, rep = super(Patch, self).assemble(datum)
        model_obj = getattr(cosmos[self.api_name].models, self.model_name)
        model_obj.validate_patch(rep)
        return self_id, rep

class URLParams(ParametrizedWrapper):
    """A Teleport type that behaves mostly like the :class:`Struct`
    type, except it serializes the data into a query string:

    .. code:: python

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

    .. code:: python

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


class APISpec(BasicWrapper):
    type_name = "cosmic.APISpec"

    schema = Struct([
        required("name", String),
        optional("homepage", String),
        required("actions", OrderedMap(Struct([
            optional("accepts", Schema),
            optional("returns", Schema),
            optional("doc", String)
        ]))),
        required("models", OrderedMap(Struct([
            required("properties", OrderedMap(Struct([
                required(u"schema", Schema),
                required(u"required", Boolean),
                optional(u"doc", String)
            ]))),
            required("links", OrderedMap(Struct([
                required(u"model", Model),
                required(u"required", Boolean),
                optional(u"doc", String)
            ]))),
            required("query_fields", OrderedMap(Struct([
                required(u"schema", Schema),
                required(u"required", Boolean),
                optional(u"doc", String)
            ]))),
            required("methods", Struct([
                required("get_by_id", Boolean),
                required("get_list", Boolean),
                required("create", Boolean),
                required("update", Boolean),
                required("delete", Boolean),
                ])),
            required("list_metadata", OrderedMap(Struct([
                required(u"schema", Schema),
                required(u"required", Boolean),
                optional(u"doc", String)
            ])))
        ])))
    ])

    @classmethod
    def assemble(cls, datum):
        from .tools import validate_underscore_identifier

        for model_name, model_spec in datum['models'].items():
            link_names = set(model_spec['links'].keys())
            field_names = set(model_spec['properties'].keys())

            if link_names & field_names:
                raise ValidationError(
                    "Model cannot contain a field and link with the same name: {}".format(model_name))

            for name in link_names | field_names:
                validate_underscore_identifier(name)

            if 'id' in link_names | field_names:
                raise ValidationError("'id' is a reserved name.")

        return datum


