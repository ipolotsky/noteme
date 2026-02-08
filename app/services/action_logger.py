"""User action logger — logs to stdout and pushes to Redis for async DB persistence."""

import json
import logging
import uuid

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("action_logger")

REDIS_ACTION_LOG_KEY = "user_actions:queue"

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url)
    return _redis


async def log_user_action(
    user_id: int,
    action: str,
    detail: str | None = None,
) -> None:
    """Log a user action to stdout + Redis queue for async DB persistence."""
    logger.info("[action] user=%s action=%s detail=%s", user_id, action, detail or "")

    record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "action": action,
        "detail": detail,
    }
    try:
        r = _get_redis()
        await r.rpush(REDIS_ACTION_LOG_KEY, json.dumps(record, ensure_ascii=False))
    except Exception:
        logger.warning("Failed to push action log to Redis", exc_info=True)
