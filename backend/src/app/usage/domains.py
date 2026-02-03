from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.common.nanoid import NanoId, NanoIdType

USAGE_PK_ABBREV = 'usg'
USAGE_DAILY_PK_ABBREV = 'usgd'
TELEMETRY_EVENT_PK_ABBREV = 'tel'


class UsageCreate(BaseModel):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=USAGE_PK_ABBREV))
    engineer_id: str
    tokens_input: int = 0
    tokens_output: int = 0
    model: str | None = None
    session_id: str | None = None

    def to_dict(self) -> dict:
        return self.model_dump()


class UsageRead(BaseModel):
    id: str
    engineer_id: str
    tokens_input: int
    tokens_output: int
    model: str | None
    session_id: str | None
    created_at: datetime

    model_config = {'from_attributes': True}

    @property
    def total_tokens(self) -> int:
        return self.tokens_input + self.tokens_output


class UsageDailyCreate(BaseModel):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=USAGE_DAILY_PK_ABBREV))
    engineer_id: str
    date: date
    total_tokens: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    session_count: int = 0

    def to_dict(self) -> dict:
        return self.model_dump()


class UsageDailyRead(BaseModel):
    id: str
    engineer_id: str
    date: date
    total_tokens: int
    tokens_input: int
    tokens_output: int
    cost_usd: float
    session_count: int
    created_at: datetime

    model_config = {'from_attributes': True}


class TelemetryEventCreate(BaseModel):
    """Raw telemetry event with full OTEL payload."""

    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=TELEMETRY_EVENT_PK_ABBREV))
    engineer_id: str
    session_id: str | None = None
    event_type: str  # 'metrics', 'traces', 'logs'

    # Queryable fields extracted from payload
    metric_name: str | None = None
    model: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float | None = None

    # Tool usage
    tool_name: str | None = None
    tool_result: str | None = None  # 'success', 'error', 'rejected'

    # Timing
    duration_ms: int | None = None
    time_to_first_token_ms: int | None = None

    # Raw payload for full granularity
    raw_payload: dict[str, Any] | None = None
    resource_attributes: dict[str, Any] | None = None
    scope_attributes: dict[str, Any] | None = None
    data_point_attributes: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        return self.model_dump()


class TelemetryEventRead(BaseModel):
    id: str
    engineer_id: str
    session_id: str | None
    event_type: str
    metric_name: str | None
    model: str | None
    tokens_input: int
    tokens_output: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cost_usd: float | None
    tool_name: str | None
    tool_result: str | None
    duration_ms: int | None
    time_to_first_token_ms: int | None
    raw_payload: dict[str, Any] | None
    resource_attributes: dict[str, Any] | None
    scope_attributes: dict[str, Any] | None
    data_point_attributes: dict[str, Any] | None
    created_at: datetime

    model_config = {'from_attributes': True}
