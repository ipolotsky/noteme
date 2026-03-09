"""Tests for wish service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate
from app.schemas.wish import WishCreate, WishUpdate
from app.services.user_service import get_or_create_user
from app.services.wish_service import (
    WishLimitError,
    count_user_wishes,
    create_wish,
    delete_wish,
    get_user_wishes,
    get_wish,
    update_wish,
)


async def _create_test_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    user, _ = await get_or_create_user(session, data)
    return user


@pytest.mark.asyncio
async def test_create_wish(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)

    data = WishCreate(text="Max wants Sony headphones", person_names=["Max"])
    wish = await create_wish(session, user_id, data)

    assert wish.text == "Max wants Sony headphones"
    assert len(wish.people) == 1
    assert wish.people[0].name == "Max"


@pytest.mark.asyncio
async def test_wish_limit(session: AsyncSession, user_id: int):
    user = await _create_test_user(session, user_id)
    user.max_wishes = 2
    await session.flush()

    for i in range(2):
        data = WishCreate(text=f"Wish {i}")
        await create_wish(session, user_id, data)

    with pytest.raises(WishLimitError):
        data = WishCreate(text="Overflow")
        await create_wish(session, user_id, data)


@pytest.mark.asyncio
async def test_update_wish(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    data = WishCreate(text="Original")
    wish = await create_wish(session, user_id, data)

    updated = await update_wish(session, wish.id, WishUpdate(text="Updated"))
    assert updated is not None
    assert updated.text == "Updated"


@pytest.mark.asyncio
async def test_delete_wish(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    data = WishCreate(text="Temp wish")
    wish = await create_wish(session, user_id, data)

    assert await delete_wish(session, wish.id) is True
    assert await get_wish(session, wish.id) is None


@pytest.mark.asyncio
async def test_get_user_wishes(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    for i in range(3):
        data = WishCreate(text=f"Wish {i}")
        await create_wish(session, user_id, data)

    wishes = await get_user_wishes(session, user_id)
    assert len(wishes) == 3
    count = await count_user_wishes(session, user_id)
    assert count == 3


@pytest.mark.asyncio
async def test_wish_limit_bypassed_by_subscription(session: AsyncSession, user_id: int):
    from app.services.subscription_service import grant_subscription

    user = await _create_test_user(session, user_id)
    user.max_wishes = 2
    await session.flush()

    for i in range(2):
        data = WishCreate(text=f"Wish {i}")
        await create_wish(session, user_id, data)

    await grant_subscription(session, user_id, months=1, source="admin")

    data = WishCreate(text="Extra wish")
    wish = await create_wish(session, user_id, data)
    assert wish.text == "Extra wish"
