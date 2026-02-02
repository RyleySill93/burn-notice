from loguru import logger

from src import settings
from src.app.leaderboard.domains import Leaderboard, LeaderboardEntry
from src.platform.slack.client import get_slack_client


class SlackService:
    @staticmethod
    def format_tokens(n: int) -> str:
        """Format token count for display."""
        if n >= 1_000_000:
            return f'{n / 1_000_000:.1f}M'
        if n >= 1_000:
            return f'{n / 1_000:.0f}K'
        return str(n)

    @staticmethod
    def rank_change_icon(entry: LeaderboardEntry) -> str:
        """Get icon showing rank change."""
        change = entry.rank_change
        if change is None:
            return '🆕'
        if change > 0:
            return f'▲{change}'
        if change < 0:
            return f'▼{abs(change)}'
        return '━'

    @staticmethod
    def format_leaderboard_section(title: str, entries: list[LeaderboardEntry], limit: int = 5) -> str:
        """Format a leaderboard section as Slack mrkdwn."""
        if not entries:
            return f'*{title}*\n_No data yet_'

        lines = [f'*{title}*', '```']
        for entry in entries[:limit]:
            change = SlackService.rank_change_icon(entry)
            tokens = SlackService.format_tokens(entry.tokens)
            lines.append(f'{entry.rank:>2}. {entry.display_name:<16} {tokens:>8}  {change}')
        lines.append('```')
        return '\n'.join(lines)

    @staticmethod
    def build_slack_message(leaderboard: Leaderboard) -> dict:
        """Build Slack Block Kit message."""
        date_str = leaderboard.date.strftime('%A, %b %d, %Y')

        blocks = [
            {
                'type': 'header',
                'text': {'type': 'plain_text', 'text': '🔥 burn-notice', 'emoji': True},
            },
            {
                'type': 'context',
                'elements': [{'type': 'mrkdwn', 'text': date_str}],
            },
            {'type': 'divider'},
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': SlackService.format_leaderboard_section('📅 Daily', leaderboard.daily),
                },
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': SlackService.format_leaderboard_section('📆 Weekly', leaderboard.weekly),
                },
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': SlackService.format_leaderboard_section('📊 Monthly', leaderboard.monthly),
                },
            },
            {'type': 'divider'},
            {
                'type': 'context',
                'elements': [
                    {
                        'type': 'mrkdwn',
                        'text': '▲ = moved up · ▼ = moved down · ━ = no change · 🆕 = new',
                    }
                ],
            },
        ]

        return {'blocks': blocks}

    @staticmethod
    def post_leaderboard(leaderboard: Leaderboard, webhook_url: str | None = None) -> bool:
        """Post leaderboard to Slack."""
        webhook_url = webhook_url or settings.SLACK_LEADERBOARD_WEBHOOK_URL
        if not webhook_url:
            logger.warning('No Slack webhook URL configured, skipping post')
            return False

        message = SlackService.build_slack_message(leaderboard)
        client = get_slack_client()

        logger.info(f'Posting leaderboard for {leaderboard.date}')
        return client.post_webhook(webhook_url, message)
