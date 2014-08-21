__all__ = ['BaseModel']


class BaseModel(object):
    """Subclasses of this class are fed into the :meth:`~cosmic.api.API.model`
    decorator to attach models to an API. The API object doesn't care about
    how you implement this class, it just copies the necessary properties and
    leaves the class alone.
    """
    #: A list of properties which, along with
    #: :data:`~cosmic.models.BaseModel.links` below, will be used for the
    #: model's representation and patch, defined in the same way Teleport
    #: Struct fields are defined:
    #:
    #: .. code:: python
    #:
    #:     properties = [
    #:         required('name', String),
    #:         optional('age', Integer),
    #:     ]
    #:
    #: See :class:`~cosmic.types.Representation` and
    #: :class:`~cosmic.types.Patch`.
    properties = []
    #: A list of methods that this model supports. Possible values are
    #: ``'get_by_id'``, ``'create'``, ``'update'``, ``'delete'`` and
    #: ``'get_list'``.
    methods = []
    #: A list of properties for the :meth:`get_list` handler. They are defined
    #: in the same way as :data:`properties` above.
    query_fields = []
    #: A list of properties that can be returned along with the usual response
    #: for :meth:`~cosmic.models.BaseModel.get_list`. These can be used for
    #: things like pagination.
    list_metadata = []
    #: Similar to properties, but encodes a relationship between this model
    #: and another. In database terms this would be a foreign key. Use
    #: :func:`~cosmic.types.required_link` and
    #: :func:`~cosmic.types.optional_link` to specify them.
    links = []

    @classmethod
    def get_by_id(cls, id):
        """
        :param id:
        :return: Model representation
        :raises cosmic.exceptions.NotFound:
        """
        raise NotImplementedError()

    @classmethod
    def get_list(cls, **kwargs):
        """
        :param kwargs: Defined by \
            :data:`~cosmic.models.BaseModel.query_fields`
        :return: If model does not define \
            :data:`~cosmic.models.BaseModel.list_metadata`, returns a list of
            tuples of models ids and representations. Otherwise returns a
            tuple where the first element is the above list, and the second is
            a dict as specified by \
            :data:`~cosmic.models.BaseModel.list_metadata`.
        """
        raise NotImplementedError()

    @classmethod
    def create(cls, **valid_patch):
        """
        :param validated_patch: The model patch.
        :return: A tuple of model id and model representation.
        """
        raise NotImplementedError()

    @classmethod
    def update(cls, id, **valid_patch):
        """
        :param id:
        :param validated_patch:
        :return: The model representation after patch has been applied.
        :raises cosmic.exceptions.NotFound:
        """
        raise NotImplementedError()

    @classmethod
    def delete(cls, id):
        """
        :param id:
        :raises cosmic.exceptions.NotFound:
        """
        raise NotImplementedError()

    @classmethod
    def validate_patch(cls, patch):
        """
        :param patch: The model patch
        :raises cosmic.exceptions.ValidationError:

        Run before any :meth:`~cosmic.models.BaseModel.create` or
        :meth:`~cosmic.models.BaseModel.update` call to validate the patch.
        All fields are made optional for the patch, so this method is a chance
        to ensure that the expected values were indeed passed in.
        """
        pass

