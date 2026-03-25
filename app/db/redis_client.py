from app.core.config import settings
from redis import Redis
from redis.exceptions import RedisError

_client: Redis | None = None


def get_redis_client() -> Redis | None:
    """
    Return a reusable Redis client.

    If Redis is unavailable, return None so the rest of the application
    can gracefully fall back to database-only behavior.
    """
    global _client

    if _client is not None:
        return _client

    try:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
        _client.ping()
    except RedisError:
        _client = None

    return _client
