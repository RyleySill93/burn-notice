from functools import wraps
from typing import Any, Callable, TypeVar

from dramatiq.message import Message
from fastapi import APIRouter, HTTPException, status

from src.network.queue.domains import SignedMessageKey, SignedMessageKeyDomain, TaskResultDomain
from src.network.queue.models import JobStatus
from src.network.queue.results import get_result_from_message_key, sign_message

api_router = APIRouter()

T = TypeVar('T', bound=Callable[..., Message])


def task_status_route(router: T) -> Callable[..., SignedMessageKeyDomain]:
    """
    Decorator for task route; returns a signed message key for polling

    Example usage:

        @api_router.post('/create-document')
        @task_status_route
        async def create_document() -> Message:
            return create_document_task.send()

    The FE can then poll the task status using the signed message key using get_task_status.
    """

    @wraps(router)
    def result(*args: Any, **kwargs: Any) -> SignedMessageKeyDomain:
        message = router(*args, **kwargs)
        signed = sign_message(message)
        return SignedMessageKeyDomain(signed_message_key=str(signed))

    # Update return type annotation so the generated client type is correct
    result.__annotations__['return'] = SignedMessageKeyDomain

    return result


@api_router.get('/task/{signed_message_key}', dependencies=[])
async def get_task_status(signed_message_key: str) -> TaskResultDomain:
    try:
        signed = SignedMessageKey.read(signed_message_key)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid message signature')

    job_status = JobStatus.get_or_none(job_id=signed.message_key)
    if not job_status:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found')

    if job_status.status == 'COMPLETED':
        result = get_result_from_message_key(signed.message_key)

        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task result not found')

        return TaskResultDomain(status=job_status, result=result)

    return TaskResultDomain(status=job_status)
