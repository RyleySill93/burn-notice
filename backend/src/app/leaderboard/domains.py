from datetime import date

from pydantic import BaseModel, computed_field


class LeaderboardEntry(BaseModel):
    engineer_id: str
    display_name: str
    tokens: int
    rank: int
    prev_rank: int | None = None

    @computed_field
    @property
    def rank_change(self) -> int | None:
        """Positive = moved up, negative = moved down, None = new."""
        if self.prev_rank is None:
            return None
        return self.prev_rank - self.rank


class Leaderboard(BaseModel):
    date: date
    daily: list[LeaderboardEntry]
    weekly: list[LeaderboardEntry]
    monthly: list[LeaderboardEntry]
