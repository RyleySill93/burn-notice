import datetime
from typing import Any, Dict, List
from uuid import UUID

import pytz
from pydantic import field_validator

from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType


class AuditEventRead(BaseDomain):
    id: UUID
    txn_id: int
    request_id: NanoIdType | None = None
    breadcrumb: str | None = None
    user_id: NanoIdType | None = None
    occurred_at: datetime.datetime
    event_type: str | None = None
    context: dict | None = None

    @field_validator('occurred_at')
    def set_timezone(cls, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=pytz.UTC)

        return value


class AuditLogRead(BaseDomain):
    id: UUID
    event_id: UUID
    event: AuditEventRead
    table_name: str
    operation_type: str
    context: dict | None = None
    row_data: dict | None = None
    changed_data: dict | None = None


class AuditRow(BaseDomain):
    id: UUID
    event_id: UUID
    item_type: str
    operation_type: str
    occurred_at: datetime.datetime
    user_display_name: str
    event_context: dict | None = None


class AuditEventDomain(BaseDomain):
    event_id: UUID
    user_display_name: str
    occurred_at: datetime.datetime
    event_context: Dict[str, Any] | None = None
    total_logs_count: int
    logs: List[Any]


class PaginatedResult(BaseDomain):
    events: List[AuditEventDomain]
    current_page: int
    total_pages: int
    page_size: int
