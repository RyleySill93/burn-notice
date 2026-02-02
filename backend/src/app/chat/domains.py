from src.common.domain import BaseDomain


class ChatMessageCreate(BaseDomain):
    """Domain for creating a chat message"""

    user_id: str
    message: str


class ChatMessageResponse(BaseDomain):
    """Domain for chat message response"""

    success: bool
    message: str = 'Message queued for processing'
