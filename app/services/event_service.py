import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event, EventPerson
from app.models.person import Person
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate
from app.services.person_service import get_or_create_people


class EventLimitError(Exception):
    def __init__(self, max_events: int):
        self.max_events = max_events
        super().__init__(f"Event limit reached: {max_events}")


async def get_event(
    session: AsyncSession, event_id: uuid.UUID, user_id: int | None = None
) -> Event | None:
    stmt = select(Event).options(selectinload(Event.people)).where(Event.id == event_id)
    if user_id is not None:
        stmt = stmt.where(Event.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_events(
    session: AsyncSession, user_id: int, offset: int = 0, limit: int = 10
) -> list[Event]:
    result = await session.execute(
        select(Event)
        .options(selectinload(Event.people))
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


async def create_event(session: AsyncSession, user_id: int, data: EventCreate) -> Event:
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    from app.services.app_settings_service import get_int_setting

    max_events = await get_int_setting(session, "default_max_events", user.max_events)
    count = await count_user_events(session, user_id)
    if count >= max_events:
        from app.services.subscription_service import has_active_subscription

        if not await has_active_subscription(session, user_id):
            raise EventLimitError(max_events)

    people = []
    if data.person_names:
        people = await get_or_create_people(session, user_id, data.person_names)

    event = Event(
        user_id=user_id,
        title=data.title,
        event_date=data.event_date,
        description=data.description,
        is_system=data.is_system,
        people=people,
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
    person_names = update_data.pop("person_names", None)

    for field, value in update_data.items():
        setattr(event, field, value)

    if person_names is not None:
        people = await get_or_create_people(session, event.user_id, person_names)
        event.people = people

    await session.flush()
    return event


async def delete_event(
    session: AsyncSession, event_id: uuid.UUID, user_id: int | None = None
) -> bool:
    event = await get_event(session, event_id, user_id=user_id)
    if event is None:
        return False
    if event.is_system:
        return False
    await session.delete(event)
    await session.flush()
    return True


async def get_events_by_person_names(
    session: AsyncSession, user_id: int, person_names: list[str], limit: int = 10
) -> list[Event]:
    result = await session.execute(
        select(Event)
        .options(selectinload(Event.people))
        .join(EventPerson, Event.id == EventPerson.event_id)
        .join(Person, EventPerson.person_id == Person.id)
        .where(
            Event.user_id == user_id,
            func.lower(Person.name).in_([n.lower() for n in person_names]),
        )
        .distinct()
        .order_by(Event.event_date.desc())
        .limit(limit)
    )
    return list(result.scalars().unique().all())
