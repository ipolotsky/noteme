"""Tests for tag service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate
from app.services.tag_service import (
    create_tag,
    delete_tag,
    get_or_create_tags,
    get_tag_by_name,
    get_user_tags,
    rename_tag,
)
from app.services.user_service import get_or_create_user


async def _create_test_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    await get_or_create_user(session, data)


@pytest.mark.asyncio
async def test_create_tag(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    tag = await create_tag(session, user_id, "Max")
    assert tag.name == "Max"
    assert tag.user_id == user_id


@pytest.mark.asyncio
async def test_case_insensitive_dedup(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    tag1 = await create_tag(session, user_id, "Max")
    tag2 = await create_tag(session, user_id, "max")
    tag3 = await create_tag(session, user_id, "MAX")

    assert tag1.id == tag2.id == tag3.id


@pytest.mark.asyncio
async def test_get_or_create_tags(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    tags = await get_or_create_tags(session, user_id, ["Max", "Love", "Max"])
    assert len(tags) == 2  # "Max" deduped


@pytest.mark.asyncio
async def test_rename_tag(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    tag = await create_tag(session, user_id, "Maks")
    renamed = await rename_tag(session, tag.id, "Max")
    assert renamed is not None
    assert renamed.name == "Max"


@pytest.mark.asyncio
async def test_rename_tag_conflict(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    await create_tag(session, user_id, "Max")
    tag2 = await create_tag(session, user_id, "Maks")

    # Renaming to existing name should fail
    result = await rename_tag(session, tag2.id, "Max")
    assert result is None


@pytest.mark.asyncio
async def test_delete_tag(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    tag = await create_tag(session, user_id, "Temp")
    assert await delete_tag(session, tag.id) is True

    tags = await get_user_tags(session, user_id)
    assert len(tags) == 0


@pytest.mark.asyncio
async def test_get_tag_by_name(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    await create_tag(session, user_id, "Max")
    found = await get_tag_by_name(session, user_id, "max")
    assert found is not None
    assert found.name == "Max"
