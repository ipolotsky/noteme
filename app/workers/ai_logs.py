"""Worker task: drain AI log queue from Redis into PostgreSQL."""

import json
import logging
import uuid

import redis.asyncio as aioredis

from app.agents.ai_logger import REDIS_AI_LOG_KEY
from app.config import settings
from app.database import async_session_factory
from app.models.ai_log import AILog

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


async def persist_ai_logs_task(ctx: dict) -> int:
    """Drain up to BATCH_SIZE AI log records from Redis and insert into DB."""
    r = aioredis.from_url(settings.redis_url)
    count = 0
    try:
        records: list[dict] = []
        for _ in range(BATCH_SIZE):
            raw = await r.lpop(REDIS_AI_LOG_KEY)
            if raw is None:
                break
            records.append(json.loads(raw))

        if not records:
            return 0

        async with async_session_factory() as session:
            for rec in records:
                log_entry = AILog(
                    id=uuid.UUID(rec["id"]),
                    user_id=rec["user_id"],
                    agent_name=rec["agent_name"],
                    model=rec["model"],
                    request_messages=rec.get("request_messages"),
                    request_text=rec.get("request_text"),
                    response_text=rec.get("response_text"),
                    tokens_prompt=rec.get("tokens_prompt"),
                    tokens_completion=rec.get("tokens_completion"),
                    tokens_total=rec.get("tokens_total"),
                    latency_ms=rec.get("latency_ms"),
                    error=rec.get("error"),
                )
                session.add(log_entry)

            await session.commit()
            count = len(records)
            logger.info("Persisted %d AI log records to DB", count)
    except Exception:
        logger.exception("Failed to persist AI logs")
    finally:
        await r.aclose()

    return count
