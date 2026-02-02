from dramatiq.message import Message
from dramatiq.results import Results
from dramatiq.results.backends import RedisBackend

from src import settings
from src.network.queue.domains import SignedMessageKey


def get_results_backend() -> Results:
    backend = RedisBackend(url=settings.REDIS_URL)
    backend.build_message_key = lambda message: message.message_id
    return backend


def get_result_from_message_key(message_key: str):
    backend = get_results_backend()

    data = backend.client.lindex(message_key, 0)
    if data is None:
        return None

    return backend.unwrap_result(backend.encoder.decode(data))


def sign_message(message: Message):
    return SignedMessageKey.sign_message(get_results_backend().build_message_key(message))
