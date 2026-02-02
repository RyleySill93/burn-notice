import json
from datetime import datetime
from typing import Any, Dict, List

import dramatiq

from src import settings
from src.network.broadcaster.redis import SyncRedisBroadcaster
from src.network.cache.cache import Cache
from src.network.websockets.domains import WebSocketMessageDomain


@dramatiq.actor(max_retries=3)
def send_todo_notification(user_id: str, todo_id: str, action: str) -> None:
    """Send notification when a todo is created, updated, or deleted"""
    broadcaster = SyncRedisBroadcaster(settings.REDIS_URL)

    message = WebSocketMessageDomain(
        user_id=user_id,
        channel_type='TODO_UPDATE',
        payload={'action': action, 'todo_id': todo_id, 'timestamp': str(datetime.now())},
    )

    broadcaster.publish(message)
    print(f'Notification sent: {action} todo {todo_id} for user {user_id}')


@dramatiq.actor(max_retries=0)
def cache_todo(todo_data: Dict[str, Any]) -> None:
    """Cache todo data in Redis"""
    todo_id = todo_data.get('id')
    if not todo_id:
        return

    cache_key = f'todo:{todo_id}'
    # Cache for 1 hour
    Cache.setex(cache_key, 3600, json.dumps(todo_data))
    print(f'Todo {todo_id} cached')


@dramatiq.actor(max_retries=0)
def invalidate_todo_cache(todo_id: str) -> None:
    """Invalidate cached todo data"""
    cache_key = f'todo:{todo_id}'
    Cache.delete(cache_key)
    print(f'Todo {todo_id} cache invalidated')


@dramatiq.actor(max_retries=2)
def process_bulk_todos(user_id: str, todo_ids: List[str], operation: str) -> List[Dict[str, Any]]:
    """Process multiple todos in background"""
    results = []

    for todo_id in todo_ids:
        try:
            # Simulate processing
            print(f'Processing {operation} for todo {todo_id}')
            # Add your actual processing logic here
            results.append({'todo_id': todo_id, 'status': 'success'})
        except Exception as e:
            results.append({'todo_id': todo_id, 'status': 'failed', 'error': str(e)})

    # Send completion notification
    broadcaster = SyncRedisBroadcaster(settings.REDIS_URL)
    message = WebSocketMessageDomain(
        user_id=user_id, channel_type='BULK_OPERATION_COMPLETE', payload={'operation': operation, 'results': results}
    )
    broadcaster.publish(message)

    return results
