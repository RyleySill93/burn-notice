from urllib.parse import urlparse

from walrus import Walrus

from src.settings import REDIS_URL

# Parse REDIS_URL to extract components for Walrus
_parsed = urlparse(REDIS_URL)
Cache = Walrus(
    host=_parsed.hostname or 'localhost',
    port=_parsed.port or 6379,
    db=0,
    decode_responses=True,
    password=_parsed.password,
)
