from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

from src.app.engineers.service import EngineerService
from src.app.usage.domains import BackfillResponse, RollupResponse, UsageCreateRequest, UsageRead
from src.app.usage.service import UsageService
from src.core.authentication.dependencies import get_current_membership
from src.core.customer.models import Customer
from src.core.membership.domains import MembershipRead

router = APIRouter()


@router.post('', response_model=UsageRead)
def record_usage(
    request: UsageCreateRequest,
    x_team_api_key: str = Header(..., alias='X-Team-API-Key'),
) -> UsageRead:
    """
    Record token usage. Auto-registers engineer if not exists.

    Requires X-Team-API-Key header with the team's customer ID.
    This endpoint is designed for CLI/automation usage without user auth.
    """
    # Validate the team exists
    customer = Customer.get_or_none(id=x_team_api_key)
    if not customer:
        raise HTTPException(status_code=401, detail='Invalid team API key')

    # Get or create the engineer
    engineer = EngineerService.get_or_create(
        customer_id=customer.id,
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
def run_rollup(
    for_date: datetime | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> RollupResponse:
    """Manually trigger daily rollup for the team."""
    target_date = for_date.date() if for_date else (datetime.now(timezone.utc) - timedelta(days=1)).date()
    count = UsageService.rollup_daily(target_date, customer_id=membership.customer_id)

    return RollupResponse(date=target_date, engineers_processed=count)


@router.post('/backfill', response_model=BackfillResponse)
def run_backfill(
    membership: MembershipRead = Depends(get_current_membership),
) -> BackfillResponse:
    """Backfill all historical usage data into UsageDaily. Admin only."""
    return UsageService.backfill_all()
