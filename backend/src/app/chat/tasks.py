import random
import time

import dramatiq
from loguru import logger

from src.network.broadcaster.redis import SyncRedisBroadcaster
from src.network.websockets.domains import WebSocketMessageDomain
from src.settings import REDIS_URL


@dramatiq.actor(max_retries=1)
def process_chat_message(user_id: str, message: str) -> int:
    """
    Process a chat message:
    1. Sleep for 3 seconds to simulate processing
    2. Generate a random number between 1-10
    3. Send response back via WebSocket
    """
    logger.info(f'Processing chat message from user {user_id}: {message}')

    # Simulate processing delay
    time.sleep(3)

    # Generate random response
    random_number = random.randint(1, 10)
    response_text = f"I received your message: '{message}'. Here's your random number: {random_number}"

    # Send response via WebSocket
    broadcaster = SyncRedisBroadcaster(REDIS_URL)
    ws_message = WebSocketMessageDomain(
        user_id=user_id,
        channel_type='CHAT_RESPONSE',
        payload={'text': response_text, 'random_number': random_number, 'original_message': message},
    )

    broadcaster.publish(ws_message)
    logger.info(f'Sent chat response to user {user_id} with random number {random_number}')

    return random_number
