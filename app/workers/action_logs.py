"""Worker task: drain user action log queue from Redis into PostgreSQL."""

import json
import logging
import uuid

import redis.asyncio as aioredis

from app.config import settings
from app.database import async_session_factory
from app.models.user_action_log import UserActionLog
from app.services.action_logger import REDIS_ACTION_LOG_KEY

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


async def persist_action_logs_task(ctx: dict) -> int:
    """Drain up to BATCH_SIZE user action log records from Redis and insert into DB."""
    r = aioredis.from_url(settings.redis_url)
    count = 0
    try:
        records: list[dict] = []
        for _ in range(BATCH_SIZE):
            raw = await r.lpop(REDIS_ACTION_LOG_KEY)
            if raw is None:
                break
            records.append(json.loads(raw))

        if not records:
            return 0

        async with async_session_factory() as session:
            for rec in records:
                log_entry = UserActionLog(
                    id=uuid.UUID(rec["id"]),
                    user_id=rec["user_id"],
                    action=rec["action"],
                    detail=rec.get("detail"),
                )
                session.add(log_entry)

            await session.commit()
            count = len(records)
            logger.info("Persisted %d user action log records to DB", count)
    except Exception:
        logger.exception("Failed to persist user action logs")
    finally:
        await r.aclose()

    return count
