from datetime import date

from sqlalchemy import BigInteger, Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.usage.constants import (
    TELEMETRY_EVENT_PK_ABBREV,
    USAGE_DAILY_PK_ABBREV,
    USAGE_PK_ABBREV,
)
from src.app.usage.domains import (
    TelemetryEventCreate,
    TelemetryEventRead,
    UsageCreate,
    UsageDailyCreate,
    UsageDailyRead,
    UsageRead,
)
from src.common.model import BaseModel


class Usage(BaseModel[UsageRead, UsageCreate]):
    """Raw token usage event."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False, index=True)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    engineer = relationship('Engineer')

    __pk_abbrev__ = USAGE_PK_ABBREV
    __read_domain__ = UsageRead
    __create_domain__ = UsageCreate

    __table_args__ = (Index('idx_usage_engineer_created', 'engineer_id', 'created_at'),)


class UsageDaily(BaseModel[UsageDailyRead, UsageDailyCreate]):
    """Pre-aggregated daily usage totals."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tokens_input: Mapped[int] = mapped_column(BigInteger, default=0)
    tokens_output: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    session_count: Mapped[int] = mapped_column(Integer, default=0)

    engineer = relationship('Engineer')

    __pk_abbrev__ = USAGE_DAILY_PK_ABBREV
    __read_domain__ = UsageDailyRead
    __create_domain__ = UsageDailyCreate

    __table_args__ = (
        Index('idx_usage_daily_engineer_date', 'engineer_id', 'date', unique=True),
        Index('idx_usage_daily_date', 'date'),
    )


class TelemetryEvent(BaseModel[TelemetryEventRead, TelemetryEventCreate]):
    """Raw telemetry event capturing full OTEL payload with queryable fields."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'metrics', 'traces', 'logs'

    # Queryable fields extracted from payload
    metric_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Tool usage
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tool_result: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'success', 'error', 'rejected'

    # Timing
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_to_first_token_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Raw payload for full granularity - JSONB for efficient querying
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resource_attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scope_attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    data_point_attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    engineer = relationship('Engineer')

    __pk_abbrev__ = TELEMETRY_EVENT_PK_ABBREV
    __read_domain__ = TelemetryEventRead
    __create_domain__ = TelemetryEventCreate

    __table_args__ = (
        Index('idx_telemetry_engineer_created', 'engineer_id', 'created_at'),
        Index('idx_telemetry_session', 'session_id', 'created_at'),
        Index('idx_telemetry_metric_name', 'metric_name'),
        Index('idx_telemetry_model', 'model'),
    )
