import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.beautiful_date import BeautifulDate
from app.models.event import Event
from app.models.notification_log import NotificationLog
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_dates_for_day(
    session: AsyncSession, user_id: int, target_date: date
) -> list[BeautifulDate]:
    result = await session.execute(
        select(BeautifulDate)
        .join(Event, BeautifulDate.event_id == Event.id)
        .options(
            selectinload(BeautifulDate.event).selectinload(Event.people),
            selectinload(BeautifulDate.strategy),
        )
        .where(
            Event.user_id == user_id,
            BeautifulDate.target_date == target_date,
        )
        .order_by(BeautifulDate.target_date.asc())
    )
    return list(result.scalars().unique().all())


async def get_dates_for_range(
    session: AsyncSession, user_id: int, start_date: date, end_date: date
) -> list[BeautifulDate]:
    result = await session.execute(
        select(BeautifulDate)
        .join(Event, BeautifulDate.event_id == Event.id)
        .options(
            selectinload(BeautifulDate.event).selectinload(Event.people),
            selectinload(BeautifulDate.strategy),
        )
        .where(
            Event.user_id == user_id,
            BeautifulDate.target_date >= start_date,
            BeautifulDate.target_date < end_date,
        )
        .order_by(BeautifulDate.target_date.asc())
    )
    return list(result.scalars().unique().all())


async def log_notification(
    session: AsyncSession,
    user_id: int,
    notification_type: str,
    beautiful_date_id=None,
    wish_id=None,
) -> None:
    log = NotificationLog(
        user_id=user_id,
        notification_type=notification_type,
        beautiful_date_id=beautiful_date_id,
        wish_id=wish_id,
    )
    session.add(log)
    await session.flush()


async def has_notification_been_sent(
    session: AsyncSession,
    user_id: int,
    notification_type: str,
    since: datetime,
) -> bool:
    result = await session.execute(
        select(NotificationLog.id)
        .where(
            NotificationLog.user_id == user_id,
            NotificationLog.notification_type == notification_type,
            NotificationLog.sent_at >= since,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_active_notifiable_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(
            User.is_active.is_(True),
            User.notifications_enabled.is_(True),
        )
    )
    return list(result.scalars().all())
