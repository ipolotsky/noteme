"""Tests for user service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import get_or_create_user, get_user, update_user


@pytest.mark.asyncio
async def test_create_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    user, created = await get_or_create_user(session, data)

    assert created is True
    assert user.id == user_id
    assert user.username == "testuser"
    assert user.first_name == "Test"
    assert user.language == "ru"
    assert user.max_events == 10
    assert user.max_notes == 10


@pytest.mark.asyncio
async def test_get_existing_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    await get_or_create_user(session, data)

    user, created = await get_or_create_user(session, data)
    assert created is False
    assert user.id == user_id


@pytest.mark.asyncio
async def test_update_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    await get_or_create_user(session, data)

    update = UserUpdate(language="en", notifications_enabled=False)
    user = await update_user(session, user_id, update)

    assert user is not None
    assert user.language == "en"
    assert user.notifications_enabled is False


@pytest.mark.asyncio
async def test_get_nonexistent_user(session: AsyncSession):
    user = await get_user(session, 999999999)
    assert user is None
