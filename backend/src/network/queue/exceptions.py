"""Dramatiq-specific exceptions for queue operations."""

from src.common.exceptions import InternalException


class DramatiqException(InternalException):
    """
    Base exception for Dramatiq tasks that need explicit retry control.

    When raising this exception, you MUST specify whether it's retryable or not.
    This determines whether the exception will be sent to Sentry:
    - retryable=True: Expected failure that will retry, NOT sent to Sentry
    - retryable=False: Permanent failure, WILL be sent to Sentry

    Example:
        raise DramatiqException("Job still processing", retryable=True)  # Won't go to Sentry
        raise DramatiqException("Invalid data format", retryable=False)  # Will go to Sentry
    """

    def __init__(self, message: str, *, retryable: bool, context: dict = None):
        """
        Initialize DramatiqException.

        Args:
            message: Error message
            retryable: REQUIRED - Whether this error should trigger a retry
            context: Optional context dictionary
        """
        super().__init__(message, context)
        self.retryable = retryable
        # Set is_retryable for SentryMiddleware detection
        self.is_retryable = retryable
