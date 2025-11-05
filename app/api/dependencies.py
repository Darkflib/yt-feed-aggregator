"""FastAPI dependencies for API routers."""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis

from app.config import get_settings

_redis_client: Redis | None = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Dependency for FastAPI routes to get an async Redis connection.

    Yields:
        Async Redis client instance
    """
    global _redis_client

    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=False,
        )

    yield _redis_client
