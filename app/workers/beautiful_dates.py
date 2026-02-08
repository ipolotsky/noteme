"""arq tasks for beautiful date recalculation."""

import logging
import uuid

from app.database import async_session_factory
from app.models.event import Event
from app.services.beautiful_dates.engine import recalculate_all, recalculate_for_event

logger = logging.getLogger(__name__)


async def recalculate_event_task(ctx: dict, event_id: str) -> int:
    """Recalculate beautiful dates for a single event (async task)."""
    async with async_session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(Event).where(Event.id == uuid.UUID(event_id))
        )
        event = result.scalar_one_or_none()
        if event is None:
            logger.warning("Event %s not found for recalculation", event_id)
            return 0

        count = await recalculate_for_event(session, event)
        await session.commit()
        logger.info("Recalculated %d beautiful dates for event %s", count, event_id)
        return count


async def recalculate_all_task(ctx: dict) -> int:
    """Recalculate beautiful dates for ALL events (e.g., after strategy change)."""
    async with async_session_factory() as session:
        count = await recalculate_all(session)
        await session.commit()
        logger.info("Recalculated %d total beautiful dates", count)
        return count
