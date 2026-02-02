from sqlalchemy import JSON, UUID, BigInteger, Column, DateTime, ForeignKey, Index, String, and_, desc, func, or_, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.model import BaseModel
from src.common.nanoid import NanoIdType
from src.platform.audit.domain import AuditEventRead, AuditLogRead


class AuditEvent(BaseModel[AuditEventRead, None]):
    id: Mapped[UUID] = mapped_column(UUID, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(length=50), nullable=True)
    txn_id: Mapped[int] = mapped_column(BigInteger)
    breadcrumb: Mapped[str] = mapped_column(nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), nullable=True)
    occurred_at: Mapped[NanoIdType] = mapped_column(DateTime)
    event_type: Mapped[NanoIdType] = mapped_column(String(length=255), nullable=True)
    context = Column(JSON, nullable=True)
    __read_domain__ = AuditEventRead


class AuditLog(BaseModel[AuditLogRead, None]):
    id: Mapped[UUID] = mapped_column(UUID, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey(AuditEvent.id, ondelete='CASCADE'))
    table_name: Mapped[str] = mapped_column(String)
    # Object attributes
    operation_type: Mapped[str] = mapped_column(String(length=50))
    context = Column(JSONB, comment='Object contains information to query')
    row_data = Column(JSON, comment='Data of the row before the operation')
    # For updates
    changed_data = Column(JSON, comment='Changes from the operation')
    event = relationship('AuditEvent', backref='event', lazy='joined', viewonly=True)

    __read_domain__ = AuditLogRead

    __table_args__ = (
        # Basic table_name index for general queries
        Index('ix_auditlog_table_name', 'table_name'),
        # Specific index for field value lookups
        Index(
            'ix_auditlog_field_value_lookup',
            'table_name',
            text("(context ->> 'field_value_id')"),
            desc('created_at'),
            postgresql_where=text("table_name = 'fieldvalue'"),
        ),
        # Specific index for field lookups
        Index(
            'ix_auditlog_field_lookup',
            'table_name',
            text("(context ->> 'field_id')"),
            desc('created_at'),
            postgresql_where=text("table_name = 'field'"),
        ),
        Index(
            'ix_auditlog_temporal_model_entity',
            'table_name',
            text("(context ->> 'is_temporal')"),
            text("(context ->> 'model_id')"),
            text("(context ->> 'entity_id')"),
            desc('created_at'),
            postgresql_where=text("table_name = 'fieldvalue'"),
        ),
        Index(
            'ix_auditlog_temporal_model_namespace',
            'table_name',
            text("(context ->> 'is_temporal')"),
            text("(context ->> 'model_id')"),
            text("(context ->> 'namespace_id')"),
            desc('created_at'),
            postgresql_where=text("table_name = 'field'"),
        ),
        Index(
            'ix_auditlog_document_id',
            'table_name',
            text("(context ->> 'document_id')"),
            desc('created_at'),
            postgresql_where=text("table_name IN ('document', 'documenttaglink')"),
        ),
        Index(
            'ix_auditlog_document_tag_id',
            'table_name',
            text("(context ->> 'document_tag_id')"),
            desc('created_at'),
            postgresql_where=text("table_name = 'documenttag'"),
        ),
        Index(
            'ix_auditlog_entity_id',
            'table_name',
            text("(context ->> 'entity_id')"),
            desc('created_at'),
            postgresql_where=text("table_name IN ('document', 'documenttaglink')"),
        ),
        # Index for efficient field_value_id lookups
        Index(
            'ix_auditlog_fieldvalue_id',
            text("(context ->> 'field_value_id')"),
            'created_at',
            'event_id',
            postgresql_where=text("table_name = 'fieldvalue'"),
        ),
    )

    @classmethod
    def list_audit_events_for_multiple_contexts(
        cls,
        table_context_pairs: list[tuple[str, dict[str, str]]],
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AuditLogRead], int]:
        """
        Query audit logs grouped by events with multiple table + context filter combinations.

        Args:
            table_context_pairs: List of (table_names, fields) pairs where each pair creates one context filter group
            page: Page number for pagination (1-based)
            page_size: Number of events per page

        Returns:
            Tuple of (audit log results for paginated events, total event count)
        """
        # Build the filter conditions (same as before)
        grouped_lookups = {}
        for table_name, fields in table_context_pairs:
            if table_name not in grouped_lookups:
                grouped_lookups[table_name] = {}
            for field_name, field_value in fields.items():
                if field_name not in grouped_lookups[table_name]:
                    grouped_lookups[table_name][field_name] = []
                grouped_lookups[table_name][field_name].append(field_value)

        or_conditions = []
        for table_name, fields_dict in grouped_lookups.items():
            # Build AND conditions for all fields within the same table
            table_conditions = [cls.table_name == table_name]

            for field_name, values in fields_dict.items():
                if len(values) > 1:
                    # Handle chunking for large value lists
                    if len(values) > 50:
                        field_or_conditions = []
                        for i in range(0, len(values), 50):
                            chunk = values[i : i + 50]
                            field_or_conditions.append(cls.context.op('->>')(field_name).in_(chunk))
                        table_conditions.append(or_(*field_or_conditions))
                    else:
                        table_conditions.append(cls.context.op('->>')(field_name).in_(values))
                else:
                    table_conditions.append(cls.context.op('->>')(field_name) == values[0])

            # Combine all conditions for this table with AND
            or_conditions.append(and_(*table_conditions))

        combined_filter = or_(*or_conditions) if or_conditions else True

        session = cls._get_session()

        # Step 1: Get distinct event_ids that match the filter with their earliest log time
        matching_events_query = (
            session.query(cls.event_id, func.min(cls.created_at).label('earliest_log_time'))
            .filter(combined_filter)
            .group_by(cls.event_id)
            .subquery()
        )

        total_events = session.query(func.count(matching_events_query.c.event_id)).scalar() or 0

        offset = (page - 1) * page_size
        paginated_event_ids = (
            session.query(matching_events_query.c.event_id)
            .order_by(desc(matching_events_query.c.earliest_log_time))
            .limit(page_size)
            .offset(offset)
            .all()
        )

        if paginated_event_ids:
            event_id_list = [e[0] for e in paginated_event_ids]
            audit_logs = (
                session.query(cls)
                .filter(and_(cls.event_id.in_(event_id_list), combined_filter))
                .order_by(desc(cls.created_at))
                .all()
            )

            audit_logs = [AuditLogRead.from_orm(audit_log) for audit_log in audit_logs]
        else:
            audit_logs = []

        return audit_logs, total_events
