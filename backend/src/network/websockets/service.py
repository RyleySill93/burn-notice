from typing import Any, Optional

from sqlalchemy import event
from starlette.websockets import WebSocket

from src import settings
from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType
from src.network.broadcaster.redis import SyncRedisBroadcaster
from src.network.websockets.channels import ChannelNameEnum
from src.network.websockets.connection import ConnectionManagerType
from src.network.websockets.domains import WebSocketMessageDomain


class BroadcastDomain(BaseDomain):
    channel_name: ChannelNameEnum
    payload: BaseDomain
    specification: Optional[Any]


class WebSocketConnectionService:
    """
    Service used mainly to manage websocket connections and pub/sub
    synchronization between many server nodes. This shouldn't be used
    outside of asynchronous locations interacting directly with websocket
    connections.
    """

    def __init__(self, connection_manager: ConnectionManagerType):
        self.connection_manager: ConnectionManagerType = connection_manager

    @classmethod
    def factory(cls) -> 'WebSocketConnectionService':
        from src.network.websockets.connection import ConnectionManager

        return cls(connection_manager=ConnectionManager)

    async def connect(self, user_id: NanoIdType, websocket: WebSocket) -> str:
        """
        Subscribe a user_ids websocket to the connection manager
        """
        connection_id = await self.connection_manager.connect(
            websocket=websocket,
            user_id=user_id,
        )
        return connection_id

    async def disconnect(self, user_id: NanoIdType, connection_id: str):
        """
        Unsubscribe a websocket by user_id and connection_id
        """
        await self.connection_manager.disconnect(
            connection_id=connection_id,
            user_id=user_id,
        )

    async def publish(self, message: WebSocketMessageDomain):
        """
        Broadcast a websocket message across all server nodes via
        the connection manager.
        """
        await self.connection_manager.publish(message)


class WebSocketService:
    """
    The primary service synchronous actions will interact with for sending
    websocket messages to connected websockets held by the http servers.

    example:
        websocket_service = WebSocketService.factory()
        message = WebSocketMessageDomain(
            code=200,
            user_id="user-123",
            channel_type='SYSTEM',
            payload={"message": 'From the synchronous lands'},
        )
        websocket_service.publish(message)
    """

    def __init__(self, connection_broadcaster: SyncRedisBroadcaster):
        self.connection_broadcaster: SyncRedisBroadcaster = connection_broadcaster

    @classmethod
    def factory(cls) -> 'WebSocketService':
        return cls(connection_broadcaster=SyncRedisBroadcaster(settings.REDIS_URL))

    def publish(self, message: WebSocketMessageDomain):
        self.connection_broadcaster.publish(message)

    def publish_on_commit(self, message: WebSocketMessageDomain):
        """
        Queue a message to be broadcast after the commit of the current transaction.
        """
        from src.network.database.session import db

        @event.listens_for(db.session, 'after_commit')
        def receive_after_commit(session):
            self.publish(message)

        @event.listens_for(db.session, 'after_soft_rollback', once=True)
        def _remove_event_listener_on_rollback(session, prev_transaction):
            event.remove(session, 'after_commit', receive_after_commit)
