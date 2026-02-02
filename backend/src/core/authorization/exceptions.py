# Permission-related exceptions
class PermissionError(Exception):
    """Base exception for permission-related errors"""

    pass


class ResourceNotFoundError(PermissionError):
    """Exception raised when a referenced resource does not exist"""

    pass


class InvalidSelectorError(PermissionError):
    """Exception raised when a resource selector is invalid"""

    pass
