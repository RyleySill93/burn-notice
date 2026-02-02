import logging
from urllib.parse import urlparse

import redis
from broadcaster import Broadcast
from loguru import logger

from src.network.websockets.domains import WebSocketMessageDomain
from src.settings import REDIS_URL

# Suppressing redis connecting success messages
logging.getLogger('asyncio_redis').setLevel(logging.WARNING)

# Each server subscribes and connects to this channel
BROADCAST_CHANNEL = 'SHARED'

# Set during setup
broadcaster: Broadcast | None = None


def initialize() -> None:
    global broadcaster
    if broadcaster is not None:
        # API Tests will trigger this but normal application startup should not
        logger.warning('Redis Broadcaster is already initialized')

    logger.info('Broadcasting initialized')
    broadcaster = Broadcast(url=REDIS_URL)


async def teardown() -> None:
    global broadcaster
    if broadcaster is not None:
        await broadcaster.disconnect()

    logger.info('Redis broadcaster torn down')


class SyncRedisBroadcaster:
    """
    This backend is used to synchronously broadcast
    """

    def __init__(self, url: str):
        parsed_url = urlparse(url)
        self._host = parsed_url.hostname or 'localhost'
        self._port = parsed_url.port or 6379
        self._pub_conn = redis.StrictRedis(host=self._host, port=self._port)

    def publish(self, message: WebSocketMessageDomain) -> None:
        json_message = message.model_dump_json()
        if self._pub_conn is None:
            raise ConnectionError('Not connected to Redis')
        self._pub_conn.publish(BROADCAST_CHANNEL, json_message)
