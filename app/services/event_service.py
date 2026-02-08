"""Event service — CRUD with tags and limit checking."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate
from app.services.tag_service import get_or_create_tags


class EventLimitError(Exception):
    def __init__(self, max_events: int):
        self.max_events = max_events
        super().__init__(f"Event limit reached: {max_events}")


async def get_event(
    session: AsyncSession, event_id: uuid.UUID, user_id: int | None = None
) -> Event | None:
    stmt = select(Event).options(selectinload(Event.tags)).where(Event.id == event_id)
    if user_id is not None:
        stmt = stmt.where(Event.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_events(
    session: AsyncSession, user_id: int, offset: int = 0, limit: int = 10
) -> list[Event]:
    result = await session.execute(
        select(Event)
        .options(selectinload(Event.tags))
        .where(Event.user_id == user_id)
        .order_by(Event.event_date.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().unique().all())


async def count_user_events(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(Event).where(Event.user_id == user_id)
    )
    return result.scalar_one()


async def create_event(
    session: AsyncSession, user_id: int, data: EventCreate
) -> Event:
    # Check limit
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    count = await count_user_events(session, user_id)
    if count >= user.max_events:
        raise EventLimitError(user.max_events)

    # Resolve tags first (before creating event to avoid lazy-load issues)
    tags = []
    if data.tag_names:
        tags = await get_or_create_tags(session, user_id, data.tag_names)

    event = Event(
        user_id=user_id,
        title=data.title,
        event_date=data.event_date,
        description=data.description,
        is_system=data.is_system,
        tags=tags,
    )
    session.add(event)
    await session.flush()

    return event


async def update_event(
    session: AsyncSession, event_id: uuid.UUID, data: EventUpdate, user_id: int | None = None
) -> Event | None:
    event = await get_event(session, event_id, user_id=user_id)
    if event is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    tag_names = update_data.pop("tag_names", None)

    for field, value in update_data.items():
        setattr(event, field, value)

    if tag_names is not None:
        tags = await get_or_create_tags(session, event.user_id, tag_names)
        # event.tags is already loaded via selectinload in get_event
        event.tags = tags

    await session.flush()
    return event


async def delete_event(
    session: AsyncSession, event_id: uuid.UUID, user_id: int | None = None
) -> bool:
    event = await get_event(session, event_id, user_id=user_id)
    if event is None:
        return False
    if event.is_system:
        return False  # Cannot delete system events
    await session.delete(event)
    await session.flush()
    return True
