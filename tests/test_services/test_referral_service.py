"""Tests for referral service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings
from app.schemas.user import UserCreate
from app.services.referral_service import (
    get_referral_link,
    get_referral_stats,
    process_referral,
)
from app.services.subscription_service import has_active_subscription
from app.services.user_service import get_or_create_user


async def _create_test_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username=f"user{user_id}", first_name="Test")
    user, _ = await get_or_create_user(session, data)
    return user


@pytest.mark.asyncio
async def test_process_referral(session: AsyncSession):
    referrer = await _create_test_user(session, 111)
    referred = await _create_test_user(session, 222)

    result = await process_referral(session, referrer.id, referred.id)
    assert result is True
    assert await has_active_subscription(session, referrer.id) is True


@pytest.mark.asyncio
async def test_process_referral_duplicate(session: AsyncSession):
    referrer = await _create_test_user(session, 111)
    referred = await _create_test_user(session, 222)

    await process_referral(session, referrer.id, referred.id)
    result = await process_referral(session, referrer.id, referred.id)
    assert result is False


@pytest.mark.asyncio
async def test_get_referral_link():
    link = get_referral_link("testbot", 123)
    assert link == "https://t.me/testbot?start=ref_123"


@pytest.mark.asyncio
async def test_get_referral_stats_empty(session: AsyncSession):
    await _create_test_user(session, 111)
    stats = await get_referral_stats(session, 111)
    assert stats["referral_count"] == 0


@pytest.mark.asyncio
async def test_get_referral_stats_with_referrals(session: AsyncSession):
    referrer = await _create_test_user(session, 111)
    for uid in [222, 333, 444]:
        await _create_test_user(session, uid)
        await process_referral(session, referrer.id, uid)

    stats = await get_referral_stats(session, referrer.id)
    assert stats["referral_count"] == 3


@pytest.mark.asyncio
async def test_referral_reward_months_from_settings(session: AsyncSession):
    session.add(AppSettings(key="referral_reward_months", value="3"))
    await session.flush()

    referrer = await _create_test_user(session, 111)
    referred = await _create_test_user(session, 222)

    await process_referral(session, referrer.id, referred.id)
    from app.services.subscription_service import get_active_subscription

    sub = await get_active_subscription(session, referrer.id)
    assert sub is not None
