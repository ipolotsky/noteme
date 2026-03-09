"""Periodic cleanup tasks."""

import logging
from datetime import date

from sqlalchemy import delete

from app.database import async_session_factory
from app.models.beautiful_date import BeautifulDate

logger = logging.getLogger(__name__)


async def cleanup_past_beautiful_dates(ctx: dict) -> int:
    """Delete beautiful dates with target_date in the past."""
    async with async_session_factory() as session:
        result = await session.execute(
            delete(BeautifulDate).where(BeautifulDate.target_date < date.today())
        )
        await session.commit()
        count = result.rowcount
        if count:
            logger.info("Cleaned up %d past beautiful dates", count)
        return count


async def deactivate_expired_subscriptions_task(ctx: dict) -> int:
    """Deactivate subscriptions past their expiry date."""
    from app.services.subscription_service import deactivate_expired_subscriptions

    async with async_session_factory() as session:
        count = await deactivate_expired_subscriptions(session)
        await session.commit()
        if count:
            logger.info("Deactivated %d expired subscriptions", count)
        return count
