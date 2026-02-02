from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.app.engineers.service import EngineerService
from src.app.usage.domains import UsageRead
from src.app.usage.service import UsageService

router = APIRouter()


class UsageCreateRequest(BaseModel):
    external_id: str  # Engineer's external ID
    display_name: str  # Engineer's display name (for auto-registration)
    tokens_input: int = 0
    tokens_output: int = 0
    model: str | None = None
    session_id: str | None = None


class RollupResponse(BaseModel):
    date: date
    engineers_processed: int


@router.post('', response_model=UsageRead)
def record_usage(request: UsageCreateRequest) -> UsageRead:
    """Record token usage. Auto-registers engineer if not exists."""
    # Get or create the engineer
    engineer = EngineerService.get_or_create(
        external_id=request.external_id,
        display_name=request.display_name,
    )

    return UsageService.record_usage(
        engineer_id=engineer.id,
        tokens_input=request.tokens_input,
        tokens_output=request.tokens_output,
        model=request.model,
        session_id=request.session_id,
    )


@router.post('/rollup', response_model=RollupResponse)
def run_rollup(for_date: date | None = None) -> RollupResponse:
    """Manually trigger daily rollup."""
    from datetime import timedelta, timezone
    from datetime import datetime as dt

    target_date = for_date or (dt.now(timezone.utc) - timedelta(days=1)).date()
    count = UsageService.rollup_daily(target_date)

    return RollupResponse(date=target_date, engineers_processed=count)
