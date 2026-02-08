"""Redis caching for feed queries and frequently accessed data."""

import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None

FEED_CACHE_TTL = 300  # 5 minutes
FEED_COUNT_CACHE_TTL = 300


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _feed_key(user_id: int, offset: int, limit: int) -> str:
    return f"feed:{user_id}:{offset}:{limit}"


def _feed_count_key(user_id: int) -> str:
    return f"feed_count:{user_id}"


async def get_cached_feed_count(user_id: int) -> int | None:
    """Get cached feed count for a user. Returns None if not cached."""
    try:
        r = _get_redis()
        val = await r.get(_feed_count_key(user_id))
        return int(val) if val is not None else None
    except Exception:
        logger.debug("Cache miss for feed count user_id=%s", user_id)
        return None


async def set_cached_feed_count(user_id: int, count: int) -> None:
    """Cache the feed count for a user."""
    try:
        r = _get_redis()
        await r.set(_feed_count_key(user_id), str(count), ex=FEED_COUNT_CACHE_TTL)
    except Exception:
        logger.debug("Failed to cache feed count for user_id=%s", user_id)


async def invalidate_user_feed_cache(user_id: int) -> None:
    """Invalidate all feed caches for a user (call after event create/update/delete)."""
    try:
        r = _get_redis()
        # Delete count cache
        await r.delete(_feed_count_key(user_id))
        # Delete all feed page caches via pattern
        async for key in r.scan_iter(f"feed:{user_id}:*"):
            await r.delete(key)
    except Exception:
        logger.debug("Failed to invalidate feed cache for user_id=%s", user_id)


async def close_cache() -> None:
    """Close the Redis cache connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
