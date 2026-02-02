import asyncio
import traceback
from typing import Dict
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from src.network.broadcaster.redis import BROADCAST_CHANNEL
from src.network.websockets.domains import WebSocketMessageDomain


def initialize():
    global ConnectionManager
    if ConnectionManager is None:
        logger.info('WebSockets initialized')
        ConnectionManager = _ConnectionManager()
    else:
        # API Tests will trigger this but normal application startup should not
        logger.warning('Websockets are already initialized')

    return ConnectionManager


class _ConnectionManager:
    """
    This handles all websocket connections, and pub/sub message broadcasts
    across all servers.
    """

    def __init__(self):
        """
        self.connections_by_user_id:
            {
                user_id: {connection_id: WebSocket}
            }
        """
        from src.network.broadcaster.redis import broadcaster

        self.broadcaster = broadcaster
        self.connections_by_user_id: Dict[str, Dict[str, WebSocket]] = {}
        self.user_connections: Dict[str, WebSocket] = {}
        self.channel = BROADCAST_CHANNEL

    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        """
        Save a user's WebSocket connection and return the connection ID.
        """
        connection_id = str(uuid4())
        if user_id not in self.connections_by_user_id:
            self.connections_by_user_id[user_id] = {}
        self.connections_by_user_id[user_id][connection_id] = websocket
        message = WebSocketMessageDomain(
            user_id=user_id,
            channel_type='CONNECT',
            payload={'message': 'Connection successful'},
        )
        await self._send_message_to_websocket(message=message, websocket=websocket)
        return connection_id

    async def disconnect(self, user_id: str, connection_id: str):
        """
        Remove a specific WebSocket connection for a user.
        """
        user_connections = self.connections_by_user_id.get(user_id)
        if user_connections:
            user_connections.pop(connection_id, None)
            if not user_connections:
                self.connections_by_user_id.pop(user_id, None)

    async def publish(self, message: WebSocketMessageDomain):
        """
        Send a message to all servers subscribed to this channel that will
        be holding websocket connections
        """
        json_message = message.model_dump_json()
        await self.broadcaster.publish(channel=BROADCAST_CHANNEL, message=json_message)

    async def unsubscribe(self):
        await self.broadcaster.disconnect()

    async def subscribe(self):
        asyncio.create_task(self._subscribe())
        # Ensure the subscription process is complete before someone attempts to subscribe
        # not sure if this is needed
        # subscribe_task = asyncio.create_task(self._subscribe())
        # # 2s delay for subscription to complete, this causes API test failures
        # wait_for_subscribe_task = asyncio.create_task(asyncio.sleep(2))
        # await asyncio.wait([subscribe_task, wait_for_subscribe_task], return_when=asyncio.FIRST_COMPLETED)

    async def _subscribe(self):
        """
        This function subscribes to a channel and listens to event in the channel
        """
        await self.broadcaster.connect()
        async with self.broadcaster.subscribe(channel=BROADCAST_CHANNEL) as subscriber:
            """
            Listen to every event from here
            """
            async for event in subscriber:
                message = WebSocketMessageDomain.model_validate_json(event.message)
                await self._consume_events(message=message)

    async def _consume_events(self, message: WebSocketMessageDomain):
        """
        Consume a message and send to all connected clients.
        """
        user_id = message.user_id
        user_connections = self.connections_by_user_id.get(user_id, dict())
        for connection_id, connection in user_connections.items():
            # Sending to every connection for user
            is_sent = await self._send_message_to_websocket(message=message, websocket=connection)
            if is_sent is False:
                await self.disconnect(user_id=user_id, connection_id=connection_id)

    async def _send_message_to_websocket(self, message: WebSocketMessageDomain, websocket: WebSocket) -> bool:
        """
        Send a message to a WebSocket connection.
        Returns bool based on whether or not is has sent
        """
        try:
            await websocket.send_json(message.to_dict())
            logger.debug('Websocket message sent!')
            return True
        except WebSocketDisconnect:
            logger.warning('Message not sent, WebSocket is disconnected')
        except RuntimeError as e:
            logger.error(f'Message not sent, RuntimeError: {str(e)}')
        except Exception as e:
            traceback.print_exc()
            logger.error(f'Message not sent, unexpected error: {str(e)}')

        # Assume error
        return False


# This needs global state to hold onto websocket connections
ConnectionManager: _ConnectionManager | None = None

ConnectionManagerType = _ConnectionManager
