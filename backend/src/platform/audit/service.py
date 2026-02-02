import math

from src.common.utils import group_iterable_by_attribute
from src.platform.audit.domain import (
    AuditEventDomain,
    AuditLogRead,
    PaginatedResult,
)
from src.platform.audit.formatter import AuditFormatter
from src.platform.audit.models import AuditLog


class AuditService:
    def __init__(self, formatter: AuditFormatter | None = None):
        self.formatter = formatter

    @classmethod
    def factory(cls) -> 'AuditService':
        return cls()

    def list_audit_logs_for_tables_and_context_fields(
        self,
        table_context_pairs: list[tuple[str, dict[str, str]]],
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AuditLogRead], int]:
        return AuditLog.list_audit_events_for_multiple_contexts(
            table_context_pairs=table_context_pairs,
            page=page,
            page_size=page_size,
        )

    def format(self, audit_logs) -> list[any]:
        return self.formatter.format(audit_logs=audit_logs)

    def paginate(
        self, audit_logs: list[AuditLog], page: int = 1, page_size: int = 25, total_events_count: int | None = None
    ) -> PaginatedResult:
        """
        Groups audit logs by event_id and creates paginated result.
        Since logs are already paginated at the event level, this just groups them.

        Args:
            audit_logs: List of AuditLog objects (already paginated by events)
            page: Current page number (1-based)
            page_size: Number of events per page
            total_events_count: Total number of events for pagination metadata
        Returns:
            PaginatedResult containing grouped events and metadata
        """
        event_map = group_iterable_by_attribute(audit_logs, group_by_key='event_id')
        total_events_count = total_events_count or 0
        total_pages = math.ceil(total_events_count / page_size) if total_events_count > 0 else 1

        events = []
        for event_id, logs in event_map.items():
            events.append(
                AuditEventDomain(
                    event_id=event_id,
                    user_display_name=logs[0].user_display_name if logs else None,
                    occurred_at=logs[0].occurred_at if logs else None,
                    logs=logs,
                    event_context=logs[0].event_context if logs else None,
                    total_logs_count=len(logs),
                )
            )

        return PaginatedResult(
            events=events,
            current_page=page,
            total_pages=total_pages,
            page_size=page_size,
        )
