"""
Tests for leaderboard date range logic.

Ensures that weekly/monthly leaderboards show full period data when viewing
past periods, and live (up-to-today) data when viewing the current period.

This prevents regressions like the bug where navigating to a past week only
showed the first day's data because as_of (the period start) was used as
the query end_date.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from src.app.engineers.domains import EngineerCreate
from src.app.engineers.models import Engineer
from src.app.leaderboard.service import LeaderboardService
from src.app.usage.domains import UsageDailyCreate
from src.app.usage.models import UsageDaily
from src.core.customer import Customer, CustomerCreate


@pytest.fixture
def team_with_engineers(db):
    """Create a team with 3 engineers and return (customer, engineers)."""
    customer = Customer.create(CustomerCreate(name='Test Team'))
    engineers = []
    for name in ['Alice', 'Bob', 'Charlie']:
        eng = Engineer.create(
            EngineerCreate(
                customer_id=customer.id,
                external_id=f'{name.lower()}@test.com',
                display_name=name,
            )
        )
        engineers.append(eng)
    return customer, engineers


def _seed_daily(engineer_id: str, for_date: date, tokens: int):
    """Helper to create a UsageDaily record."""
    UsageDaily.create(
        UsageDailyCreate(
            engineer_id=engineer_id,
            date=for_date,
            total_tokens=tokens,
            tokens_input=tokens // 2,
            tokens_output=tokens - tokens // 2,
            cost_usd=tokens * 0.00001,
            session_count=1,
        )
    )


class TestWeeklyLeaderboardDateRanges:
    """Ensure weekly leaderboard queries the full Mon-Sun range for past weeks."""

    def test_past_week_includes_all_seven_days(self, team_with_engineers):
        """
        The exact bug that was fixed: navigating to a past week sent the Monday
        as as_of, and the backend only queried that one day.
        """
        customer, engineers = team_with_engineers
        alice, bob, charlie = engineers

        # Past week: Mon Mar 2 - Sun Mar 8
        mon = date(2026, 3, 2)
        for day_offset in range(7):
            d = mon + timedelta(days=day_offset)
            _seed_daily(alice.id, d, 100_000)  # 100K per day = 700K total
            _seed_daily(bob.id, d, 50_000)     # 50K per day = 350K total

        # Simulate frontend sending the Monday as as_of (how date picker works)
        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=mon)

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        bob_entry = next(e for e in entries if e.engineer_id == bob.id)

        assert alice_entry.tokens == 700_000, (
            f'Expected 700K (7 days × 100K), got {alice_entry.tokens}. '
            'Past week should include all 7 days, not just the as_of day.'
        )
        assert bob_entry.tokens == 350_000

    def test_past_week_as_of_midweek(self, team_with_engineers):
        """Even if as_of is a Wednesday in a past week, show the full week."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        mon = date(2026, 3, 2)
        for day_offset in range(7):
            _seed_daily(alice.id, mon + timedelta(days=day_offset), 100_000)

        # as_of is Wednesday of that past week
        wed = date(2026, 3, 4)
        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=wed)

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.tokens == 700_000

    def test_current_week_shows_live_data_up_to_today(self, team_with_engineers):
        """Current week should only include data up to today, not future days."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        # Current week is Mon Mar 16 - Sun Mar 22, "today" is Wed Mar 18
        fake_today = date(2026, 3, 18)
        mon = date(2026, 3, 16)

        # Seed all 7 days (simulating some data arriving early / from other timezones)
        for day_offset in range(7):
            _seed_daily(alice.id, mon + timedelta(days=day_offset), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=fake_today):
            entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=fake_today)

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        # Mon + Tue + Wed = 3 days × 100K = 300K
        assert alice_entry.tokens == 300_000, (
            f'Expected 300K (3 days up to today), got {alice_entry.tokens}. '
            'Current week should not include future data.'
        )

    def test_current_week_monday_shows_only_monday(self, team_with_engineers):
        """On Monday of the current week, only Monday data should show."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        mon = date(2026, 3, 16)
        _seed_daily(alice.id, mon, 200_000)
        _seed_daily(alice.id, mon + timedelta(days=1), 150_000)  # Tuesday (future)

        with patch('src.app.leaderboard.service.get_today', return_value=mon):
            entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=mon)

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.tokens == 200_000

    def test_past_week_ranking_order(self, team_with_engineers):
        """Rankings should reflect the full week totals, not partial."""
        customer, engineers = team_with_engineers
        alice, bob, charlie = engineers

        mon = date(2026, 3, 2)
        # Alice: big Monday, small rest — 500K + 6×10K = 560K
        _seed_daily(alice.id, mon, 500_000)
        for d in range(1, 7):
            _seed_daily(alice.id, mon + timedelta(days=d), 10_000)

        # Bob: consistent all week — 7×100K = 700K
        for d in range(7):
            _seed_daily(bob.id, mon + timedelta(days=d), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=mon)

        # Bob should be #1 with full week data
        assert entries[0].engineer_id == bob.id
        assert entries[0].tokens == 700_000
        assert entries[1].engineer_id == alice.id
        assert entries[1].tokens == 560_000

    def test_previous_week_comparison_uses_full_week(self, team_with_engineers):
        """Rank changes should compare against the full previous week."""
        customer, engineers = team_with_engineers
        alice, bob = engineers[0], engineers[1]

        # Two weeks ago (prev_week): Mon Feb 23 - Sun Mar 1
        prev_mon = date(2026, 2, 23)
        for d in range(7):
            _seed_daily(alice.id, prev_mon + timedelta(days=d), 50_000)  # 350K
            _seed_daily(bob.id, prev_mon + timedelta(days=d), 100_000)  # 700K

        # Last week: Mon Mar 2 - Sun Mar 8
        this_mon = date(2026, 3, 2)
        for d in range(7):
            _seed_daily(alice.id, this_mon + timedelta(days=d), 100_000)  # 700K
            _seed_daily(bob.id, this_mon + timedelta(days=d), 50_000)    # 350K

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=this_mon)

        # Alice was #2 last week, #1 this week — rank_change = +1
        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.rank == 1
        assert alice_entry.prev_rank == 2

    def test_empty_past_week(self, team_with_engineers):
        """A past week with no data should return empty list."""
        customer, _ = team_with_engineers

        mon = date(2026, 1, 5)  # Some week with no data
        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=mon)

        assert entries == []


class TestMonthlyLeaderboardDateRanges:
    """Ensure monthly leaderboard queries the full month for past months."""

    def test_past_month_includes_all_days(self, team_with_engineers):
        """Navigating to a past month should show the full month's data."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        # February 2026 has 28 days
        for day in range(1, 29):
            _seed_daily(alice.id, date(2026, 2, day), 100_000)

        # Frontend sends the 1st of the month as as_of
        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=date(2026, 2, 1))

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.tokens == 2_800_000, (
            f'Expected 2.8M (28 days × 100K), got {alice_entry.tokens}. '
            'Past month should include all days, not just the 1st.'
        )

    def test_past_month_midmonth_as_of(self, team_with_engineers):
        """Even if as_of is the 15th of a past month, show full month."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        for day in range(1, 29):
            _seed_daily(alice.id, date(2026, 2, day), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=date(2026, 2, 15))

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.tokens == 2_800_000

    def test_current_month_shows_live_data_up_to_today(self, team_with_engineers):
        """Current month should only include data up to today."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        # March 2026, "today" is March 10
        fake_today = date(2026, 3, 10)
        for day in range(1, 32):
            _seed_daily(alice.id, date(2026, 3, day), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=fake_today):
            entries = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=fake_today)

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        # Days 1-10 = 10 × 100K = 1M
        assert alice_entry.tokens == 1_000_000

    def test_current_month_first_day(self, team_with_engineers):
        """On the 1st of the current month, only day 1 data should show."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        first = date(2026, 3, 1)
        _seed_daily(alice.id, first, 200_000)
        _seed_daily(alice.id, date(2026, 3, 2), 300_000)

        with patch('src.app.leaderboard.service.get_today', return_value=first):
            entries = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=first)

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.tokens == 200_000

    def test_past_december_includes_full_month(self, team_with_engineers):
        """December edge case: month_end calculation crosses year boundary."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        for day in range(1, 32):
            _seed_daily(alice.id, date(2025, 12, day), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=date(2025, 12, 1))

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.tokens == 3_100_000  # 31 days

    def test_past_month_ranking_order(self, team_with_engineers):
        """Monthly rankings should reflect full month totals."""
        customer, engineers = team_with_engineers
        alice, bob, charlie = engineers

        # Alice: big first day, small rest — 500K + 27×10K = 770K
        _seed_daily(alice.id, date(2026, 2, 1), 500_000)
        for day in range(2, 29):
            _seed_daily(alice.id, date(2026, 2, day), 10_000)

        # Bob: consistent — 28×50K = 1.4M
        for day in range(1, 29):
            _seed_daily(bob.id, date(2026, 2, day), 50_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=date(2026, 2, 1))

        assert entries[0].engineer_id == bob.id
        assert entries[0].tokens == 1_400_000
        assert entries[1].engineer_id == alice.id
        assert entries[1].tokens == 770_000


class TestGetLeaderboardIntegration:
    """Test the top-level get_leaderboard method returns correct data for all tabs."""

    def test_past_date_weekly_tab_full_week(self, team_with_engineers):
        """get_leaderboard() with a past Monday should return full week in weekly tab."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        mon = date(2026, 3, 2)
        for d in range(7):
            _seed_daily(alice.id, mon + timedelta(days=d), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            leaderboard = LeaderboardService.get_leaderboard(customer.id, as_of=mon)

        alice_weekly = next(e for e in leaderboard.weekly if e.engineer_id == alice.id)
        assert alice_weekly.tokens == 700_000

    def test_past_date_monthly_tab_full_month(self, team_with_engineers):
        """get_leaderboard() with a past 1st should return full month in monthly tab."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        for day in range(1, 29):
            _seed_daily(alice.id, date(2026, 2, day), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            leaderboard = LeaderboardService.get_leaderboard(customer.id, as_of=date(2026, 2, 1))

        alice_monthly = next(e for e in leaderboard.monthly if e.engineer_id == alice.id)
        assert alice_monthly.tokens == 2_800_000


class TestWeeklyRecapDateRanges:
    """Test that the weekly recap also returns full week data."""

    def test_recap_past_week_full_data(self, team_with_engineers):
        """Weekly recap for a past week should show full week totals."""
        customer, engineers = team_with_engineers
        alice, bob, charlie = engineers

        mon = date(2026, 3, 2)
        for d in range(7):
            _seed_daily(alice.id, mon + timedelta(days=d), 200_000)
            _seed_daily(bob.id, mon + timedelta(days=d), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            recap = LeaderboardService.get_weekly_recap(customer.id, as_of=mon)

        assert recap.team_total_tokens == 2_100_000  # (200K + 100K) × 7
        assert recap.tokens_podium[0].display_name == 'Alice'
        assert recap.tokens_podium[0].value == 1_400_000

    def test_recap_current_week_live(self, team_with_engineers):
        """Weekly recap for the current week should show data up to today."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        fake_today = date(2026, 3, 18)  # Wednesday
        mon = date(2026, 3, 16)
        for d in range(7):
            _seed_daily(alice.id, mon + timedelta(days=d), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=fake_today):
            recap = LeaderboardService.get_weekly_recap(customer.id, as_of=fake_today)

        # Mon + Tue + Wed = 300K
        assert recap.team_total_tokens == 300_000


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_sunday_as_of_same_week(self, team_with_engineers):
        """as_of on Sunday should still show the full Mon-Sun week."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        mon = date(2026, 3, 2)
        sun = date(2026, 3, 8)
        for d in range(7):
            _seed_daily(alice.id, mon + timedelta(days=d), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=sun)

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.tokens == 700_000

    def test_last_day_of_month_as_of(self, team_with_engineers):
        """as_of on the last day of a past month should show full month."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        for day in range(1, 29):
            _seed_daily(alice.id, date(2026, 2, day), 100_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            entries = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=date(2026, 2, 28))

        alice_entry = next(e for e in entries if e.engineer_id == alice.id)
        assert alice_entry.tokens == 2_800_000

    def test_week_boundary_data_isolation(self, team_with_engineers):
        """Data from adjacent weeks should not bleed into the target week."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        # Week 1: Mar 2-8
        for d in range(7):
            _seed_daily(alice.id, date(2026, 3, 2) + timedelta(days=d), 100_000)
        # Week 2: Mar 9-15
        for d in range(7):
            _seed_daily(alice.id, date(2026, 3, 9) + timedelta(days=d), 500_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 3, 16)):
            week1 = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=date(2026, 3, 2))
            week2 = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=date(2026, 3, 9))

        week1_alice = next(e for e in week1 if e.engineer_id == alice.id)
        week2_alice = next(e for e in week2 if e.engineer_id == alice.id)

        assert week1_alice.tokens == 700_000
        assert week2_alice.tokens == 3_500_000

    def test_month_boundary_data_isolation(self, team_with_engineers):
        """Data from adjacent months should not bleed into the target month."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        # February
        for day in range(1, 29):
            _seed_daily(alice.id, date(2026, 2, day), 100_000)
        # March
        for day in range(1, 32):
            _seed_daily(alice.id, date(2026, 3, day), 500_000)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 4, 1)):
            feb = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=date(2026, 2, 1))
            mar = LeaderboardService._get_monthly_leaderboard(customer.id, as_of=date(2026, 3, 1))

        feb_alice = next(e for e in feb if e.engineer_id == alice.id)
        mar_alice = next(e for e in mar if e.engineer_id == alice.id)

        assert feb_alice.tokens == 2_800_000
        assert mar_alice.tokens == 15_500_000

    def test_consecutive_week_navigation(self, team_with_engineers):
        """Simulates clicking prev/next week — each week shows its own full data."""
        customer, engineers = team_with_engineers
        alice = engineers[0]

        # Seed 4 weeks of data with different amounts
        week_tokens = [100_000, 200_000, 300_000, 400_000]
        base_monday = date(2026, 2, 23)

        for week_idx, tokens_per_day in enumerate(week_tokens):
            mon = base_monday + timedelta(weeks=week_idx)
            for d in range(7):
                _seed_daily(alice.id, mon + timedelta(days=d), tokens_per_day)

        with patch('src.app.leaderboard.service.get_today', return_value=date(2026, 4, 1)):
            for week_idx, expected_daily in enumerate(week_tokens):
                mon = base_monday + timedelta(weeks=week_idx)
                entries = LeaderboardService._get_weekly_leaderboard(customer.id, as_of=mon)
                alice_entry = next(e for e in entries if e.engineer_id == alice.id)
                expected_total = expected_daily * 7
                assert alice_entry.tokens == expected_total, (
                    f'Week {week_idx} (starting {mon}): expected {expected_total}, got {alice_entry.tokens}'
                )
