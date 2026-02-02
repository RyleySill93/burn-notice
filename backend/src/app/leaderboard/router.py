from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.app.leaderboard.domains import Leaderboard
from src.app.leaderboard.service import LeaderboardService
from src.core.authentication.dependencies import get_current_membership
from src.core.membership.domains import MembershipRead
from src.platform.slack.service import SlackService

router = APIRouter()


class PostResponse(BaseModel):
    success: bool
    date: date


@router.get('', response_model=Leaderboard)
def get_leaderboard(
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> Leaderboard:
    """Get current leaderboard data for the team."""
    return LeaderboardService.get_leaderboard(membership.customer_id, as_of)


@router.post('/post', response_model=PostResponse)
def post_to_slack(
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> PostResponse:
    """Post leaderboard to Slack."""
    leaderboard = LeaderboardService.get_leaderboard(membership.customer_id, as_of)
    success = SlackService.post_leaderboard(leaderboard)

    return PostResponse(success=success, date=leaderboard.date)
