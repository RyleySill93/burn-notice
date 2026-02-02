from fastapi import APIRouter, HTTPException
from loguru import logger

from src.app.chat.domains import ChatMessageCreate, ChatMessageResponse
from src.app.chat.tasks import process_chat_message

router = APIRouter()


@router.post('/send')
def send_chat_message(chat_message: ChatMessageCreate) -> ChatMessageResponse:
    """
    Receive a chat message and queue it for processing via Dramatiq
    """
    try:
        # Queue the message for processing
        process_chat_message.send(user_id=chat_message.user_id, message=chat_message.message)

        logger.info(f'Queued chat message from user {chat_message.user_id}')

        return ChatMessageResponse(success=True, message='Message queued for processing')
    except Exception as e:
        logger.error(f'Failed to queue chat message: {e}')
        raise HTTPException(status_code=500, detail=f'Failed to process message: {str(e)}')
