"""
Cancellation utilities for long-running operations.

Uses Redis to coordinate cancellation signals between frontend and backend.
Works for both Dramatiq tasks and direct async operations.

Usage:
    # In a Dramatiq task or async handler
    def check_cancelled() -> bool:
        return is_cancellation_requested(operation_id)

    try:
        async for event in stream_with_cancellation(..., cancellation_check=check_cancelled):
            ...
    finally:
        clear_cancellation(operation_id)

    # From frontend/API to request cancellation
    request_cancellation(operation_id)
"""

import redis

from src import settings

# Key format: task:cancel:{operation_id}
# operation_id can be conversation_id, extraction_id, job_id, etc.
CANCEL_KEY_PREFIX = 'task:cancel:'
CANCEL_TTL_SECONDS = 300  # 5 minutes - cleanup stale keys


def _get_redis_client() -> redis.Redis:
    """Get Redis client for cancellation signals."""
    return redis.from_url(settings.REDIS_URL)


def request_cancellation(operation_id: str) -> None:
    """
    Signal that an operation should be cancelled.

    Args:
        operation_id: Unique identifier (conversation_id, extraction_id, etc.)
    """
    client = _get_redis_client()
    key = f'{CANCEL_KEY_PREFIX}{operation_id}'
    client.setex(key, CANCEL_TTL_SECONDS, '1')


def is_cancellation_requested(operation_id: str) -> bool:
    """
    Check if cancellation has been requested for this operation.

    This should be called periodically in long-running operations.

    Args:
        operation_id: Unique identifier to check

    Returns:
        True if cancellation was requested, False otherwise
    """
    client = _get_redis_client()
    key = f'{CANCEL_KEY_PREFIX}{operation_id}'
    return client.exists(key) == 1


def clear_cancellation(operation_id: str) -> None:
    """
    Clear the cancellation flag.

    Should be called in finally blocks when operation completes (success or failure).
    This prevents stale flags from affecting future operations with the same ID.

    Args:
        operation_id: Unique identifier to clear
    """
    client = _get_redis_client()
    key = f'{CANCEL_KEY_PREFIX}{operation_id}'
    client.delete(key)
