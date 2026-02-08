"""Tests for note service."""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.note import NoteCreate, NoteUpdate
from app.schemas.user import UserCreate
from app.services.note_service import (
    NoteLimitError,
    count_user_notes,
    create_note,
    delete_note,
    get_note,
    get_user_notes,
    update_note,
)
from app.services.user_service import get_or_create_user


async def _create_test_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    user, _ = await get_or_create_user(session, data)
    return user


@pytest.mark.asyncio
async def test_create_note(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    data = NoteCreate(text="Max wants Sony headphones", tag_names=["Max"])
    note = await create_note(session, user_id, data)

    assert note.text == "Max wants Sony headphones"
    assert len(note.tags) == 1
    assert note.tags[0].name == "Max"


@pytest.mark.asyncio
async def test_note_with_reminder(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    data = NoteCreate(
        text="Buy a gift",
        reminder_date=date(2025, 12, 25),
        tag_names=["Gift"],
    )
    note = await create_note(session, user_id, data)

    assert note.reminder_date == date(2025, 12, 25)
    assert note.reminder_sent is False


@pytest.mark.asyncio
async def test_note_limit(session: AsyncSession, user_id: int):
    user = await _create_test_user(session, user_id)
    user.max_notes = 2
    await session.flush()

    for i in range(2):
        data = NoteCreate(text=f"Note {i}")
        await create_note(session, user_id, data)

    with pytest.raises(NoteLimitError):
        data = NoteCreate(text="Overflow")
        await create_note(session, user_id, data)


@pytest.mark.asyncio
async def test_update_note(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    data = NoteCreate(text="Original")
    note = await create_note(session, user_id, data)

    updated = await update_note(session, note.id, NoteUpdate(text="Updated"))
    assert updated is not None
    assert updated.text == "Updated"


@pytest.mark.asyncio
async def test_delete_note(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    data = NoteCreate(text="Temp note")
    note = await create_note(session, user_id, data)

    assert await delete_note(session, note.id) is True
    assert await get_note(session, note.id) is None


@pytest.mark.asyncio
async def test_get_user_notes(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    for i in range(3):
        data = NoteCreate(text=f"Note {i}")
        await create_note(session, user_id, data)

    notes = await get_user_notes(session, user_id)
    assert len(notes) == 3
    count = await count_user_notes(session, user_id)
    assert count == 3
