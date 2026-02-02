from abc import ABC, abstractmethod

import httpx
from loguru import logger

from src import settings


class BaseSlackClient(ABC):
    @abstractmethod
    def post_webhook(self, webhook_url: str, payload: dict) -> bool:
        """Post a message to a Slack webhook."""
        pass


class SlackClient(BaseSlackClient):
    """Production Slack client using webhooks."""

    def post_webhook(self, webhook_url: str, payload: dict) -> bool:
        """Post a message to a Slack webhook."""
        try:
            response = httpx.post(webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            logger.info('Slack webhook posted successfully')
            return True
        except httpx.HTTPError as e:
            logger.error(f'Slack webhook failed: {e}')
            return False


class MockSlackClient(BaseSlackClient):
    """Mock Slack client for testing."""

    def __init__(self):
        self.messages: list[dict] = []

    def post_webhook(self, webhook_url: str, payload: dict) -> bool:
        """Store message for testing."""
        self.messages.append({'webhook_url': webhook_url, 'payload': payload})
        logger.info(f'Mock Slack webhook: {payload}')
        return True


def get_slack_client() -> BaseSlackClient:
    """Get the appropriate Slack client based on settings."""
    if settings.USE_MOCK_SLACK_CLIENT:
        return MockSlackClient()
    return SlackClient()
