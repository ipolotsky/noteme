"""AI-specific rate limiting using Redis."""

import time

import redis.asyncio as aioredis

from app.config import settings


async def check_ai_rate_limit(user_id: int) -> bool:
    """Check if user is within AI rate limits.

    Returns True if request is allowed, False if rate limited.
    Limits: 30/min, 200/hr (from settings).
    """
    r = aioredis.from_url(settings.redis_url)
    try:
        now = int(time.time())
        minute_key = f"ai_rate:{user_id}:{now // 60}"
        hour_key = f"ai_rate_hr:{user_id}:{now // 3600}"

        pipe = r.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 120)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 7200)
        results = await pipe.execute()

        minute_count = results[0]
        hour_count = results[2]

        if minute_count > settings.ai_rate_limit_per_minute:
            return False
        return hour_count <= settings.ai_rate_limit_per_hour
    finally:
        await r.aclose()
