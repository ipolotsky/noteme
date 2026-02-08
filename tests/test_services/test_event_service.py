"""Tests for event service."""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.event import EventCreate, EventUpdate
from app.schemas.user import UserCreate
from app.services.event_service import (
    EventLimitError,
    count_user_events,
    create_event,
    delete_event,
    get_event,
    get_user_events,
    update_event,
)
from app.services.user_service import get_or_create_user


async def _create_test_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    user, _ = await get_or_create_user(session, data)
    return user


@pytest.mark.asyncio
async def test_create_event(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    data = EventCreate(
        title="Wedding",
        event_date=date(2022, 8, 17),
        tag_names=["Max", "Love"],
    )
    event = await create_event(session, user_id, data)

    assert event.title == "Wedding"
    assert event.event_date == date(2022, 8, 17)
    assert len(event.tags) == 2
    assert {t.name for t in event.tags} == {"Max", "Love"}


@pytest.mark.asyncio
async def test_event_limit(session: AsyncSession, user_id: int):
    user = await _create_test_user(session, user_id)
    user.max_events = 2
    await session.flush()

    for i in range(2):
        data = EventCreate(title=f"Event {i}", event_date=date(2022, 1, i + 1))
        await create_event(session, user_id, data)

    with pytest.raises(EventLimitError):
        data = EventCreate(title="Overflow", event_date=date(2022, 1, 3))
        await create_event(session, user_id, data)


@pytest.mark.asyncio
async def test_update_event(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    data = EventCreate(title="Birthday", event_date=date(2020, 5, 10))
    event = await create_event(session, user_id, data)

    updated = await update_event(session, event.id, EventUpdate(title="Bday"))
    assert updated is not None
    assert updated.title == "Bday"


@pytest.mark.asyncio
async def test_delete_event(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    data = EventCreate(title="Temp", event_date=date(2022, 1, 1))
    event = await create_event(session, user_id, data)

    assert await delete_event(session, event.id) is True
    assert await get_event(session, event.id) is None


@pytest.mark.asyncio
async def test_cannot_delete_system_event(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    data = EventCreate(title="System", event_date=date(2022, 1, 1), is_system=True)
    event = await create_event(session, user_id, data)

    assert await delete_event(session, event.id) is False


@pytest.mark.asyncio
async def test_get_user_events(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    for i in range(3):
        data = EventCreate(title=f"Event {i}", event_date=date(2022, 1, i + 1))
        await create_event(session, user_id, data)

    events = await get_user_events(session, user_id)
    assert len(events) == 3
    count = await count_user_events(session, user_id)
    assert count == 3
