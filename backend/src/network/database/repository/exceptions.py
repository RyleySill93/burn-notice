from src.common.exceptions import InternalException


class RepositoryObjectNotFound(InternalException):
    """
    Wraps sqlalchemy exception when an object does not exist
    """

    ...


class MultipleRepositoryObjectsFound(InternalException):
    """
    Wraps sqlalchemy exception when multiple results are returned when
    only one is expected
    """

    ...


class PreventingModelTruncation(InternalException):
    """
    Throws where a table truncation was avoided
    """

    ...
