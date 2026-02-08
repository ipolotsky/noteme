"""Beautiful date service — feed queries, sharing."""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.beautiful_date import BeautifulDate
from app.models.event import Event


async def get_user_feed(
    session: AsyncSession,
    user_id: int,
    offset: int = 0,
    limit: int = 10,
    from_date: date | None = None,
) -> list[BeautifulDate]:
    """Get upcoming beautiful dates for a user, ordered by target_date."""
    if from_date is None:
        from_date = date.today()

    result = await session.execute(
        select(BeautifulDate)
        .join(Event, BeautifulDate.event_id == Event.id)
        .options(
            selectinload(BeautifulDate.event).selectinload(Event.tags),
            selectinload(BeautifulDate.strategy),
        )
        .where(
            Event.user_id == user_id,
            BeautifulDate.target_date >= from_date,
        )
        .order_by(BeautifulDate.target_date.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().unique().all())


async def count_user_feed(
    session: AsyncSession, user_id: int, from_date: date | None = None
) -> int:
    """Count total upcoming beautiful dates for a user."""
    if from_date is None:
        from_date = date.today()

    result = await session.execute(
        select(func.count())
        .select_from(BeautifulDate)
        .join(Event, BeautifulDate.event_id == Event.id)
        .where(
            Event.user_id == user_id,
            BeautifulDate.target_date >= from_date,
        )
    )
    return result.scalar_one()


async def get_event_beautiful_dates(
    session: AsyncSession,
    event_id: uuid.UUID,
    offset: int = 0,
    limit: int = 10,
) -> list[BeautifulDate]:
    """Get beautiful dates for a specific event."""
    today = date.today()
    result = await session.execute(
        select(BeautifulDate)
        .options(selectinload(BeautifulDate.strategy))
        .where(
            BeautifulDate.event_id == event_id,
            BeautifulDate.target_date >= today,
        )
        .order_by(BeautifulDate.target_date.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def generate_share_uuid(
    session: AsyncSession, beautiful_date_id: uuid.UUID
) -> uuid.UUID | None:
    """Generate a share UUID for a beautiful date (lazy, on button press)."""
    result = await session.execute(
        select(BeautifulDate).where(BeautifulDate.id == beautiful_date_id)
    )
    bd = result.scalar_one_or_none()
    if bd is None:
        return None

    if bd.share_uuid is not None:
        return bd.share_uuid

    bd.share_uuid = uuid.uuid4()
    await session.flush()
    return bd.share_uuid


async def get_by_share_uuid(
    session: AsyncSession, share_uuid: uuid.UUID
) -> BeautifulDate | None:
    """Get a beautiful date by its share UUID."""
    result = await session.execute(
        select(BeautifulDate)
        .options(
            selectinload(BeautifulDate.event),
            selectinload(BeautifulDate.strategy),
        )
        .where(BeautifulDate.share_uuid == share_uuid)
    )
    return result.scalar_one_or_none()
