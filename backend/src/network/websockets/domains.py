from typing import Any, Dict

from starlette import status

from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType


class WebSocketMessageDomain(BaseDomain):
    code: int = status.HTTP_200_OK
    user_id: NanoIdType | None = None
    channel_type: str | None = None
    payload: Dict[str, Any]
