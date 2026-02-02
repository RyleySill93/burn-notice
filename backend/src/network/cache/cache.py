from walrus import Walrus

from src.settings import REDIS_DOMAIN

Cache = Walrus(host=REDIS_DOMAIN, port=6379, db=0, decode_responses=True)
