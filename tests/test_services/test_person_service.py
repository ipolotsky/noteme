"""Tests for person service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate
from app.services.person_service import (
    create_person,
    delete_person,
    get_or_create_people,
    get_person_by_name,
    get_user_people,
    rename_person,
)
from app.services.user_service import get_or_create_user


async def _create_test_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    await get_or_create_user(session, data)


@pytest.mark.asyncio
async def test_create_person(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    person = await create_person(session, user_id, "Max")
    assert person.name == "Max"
    assert person.user_id == user_id


@pytest.mark.asyncio
async def test_case_insensitive_dedup(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    person1 = await create_person(session, user_id, "Max")
    person2 = await create_person(session, user_id, "max")
    person3 = await create_person(session, user_id, "MAX")

    assert person1.id == person2.id == person3.id


@pytest.mark.asyncio
async def test_get_or_create_people(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    people = await get_or_create_people(session, user_id, ["Max", "Love", "Max"])
    assert len(people) == 2  # "Max" deduped


@pytest.mark.asyncio
async def test_rename_person(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    person = await create_person(session, user_id, "Maks")
    renamed = await rename_person(session, person.id, "Max")
    assert renamed is not None
    assert renamed.name == "Max"


@pytest.mark.asyncio
async def test_rename_person_conflict(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    await create_person(session, user_id, "Max")
    person2 = await create_person(session, user_id, "Maks")

    result = await rename_person(session, person2.id, "Max")
    assert result is None


@pytest.mark.asyncio
async def test_delete_person(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    person = await create_person(session, user_id, "Temp")
    assert await delete_person(session, person.id) is True

    people = await get_user_people(session, user_id)
    assert len(people) == 0


@pytest.mark.asyncio
async def test_get_person_by_name(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    await create_person(session, user_id, "Max")
    found = await get_person_by_name(session, user_id, "max")
    assert found is not None
    assert found.name == "Max"
