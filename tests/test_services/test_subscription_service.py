"""Tests for subscription service."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.user import UserCreate
from app.services.subscription_service import (
    activate_subscription,
    deactivate_expired_subscriptions,
    get_active_subscription,
    get_subscription_plans,
    grant_subscription,
    has_active_subscription,
)
from app.services.user_service import get_or_create_user


async def _create_test_user(session: AsyncSession, user_id: int):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    user, _ = await get_or_create_user(session, data)
    return user


async def _create_plan(
    session: AsyncSession,
    *,
    is_lifetime: bool = False,
    duration_months: int = 1,
    price_stars: int = 100,
) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        name_ru="Test Plan",
        name_en="Test Plan",
        duration_months=duration_months,
        price_stars=price_stars,
        is_lifetime=is_lifetime,
        is_active=True,
    )
    session.add(plan)
    await session.flush()
    return plan


@pytest.mark.asyncio
async def test_no_subscription(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    assert await has_active_subscription(session, user_id) is False
    assert await get_active_subscription(session, user_id) is None


@pytest.mark.asyncio
async def test_activate_monthly(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    plan = await _create_plan(session, duration_months=1)

    sub = await activate_subscription(session, user_id, plan.id)
    assert sub.is_active is True
    assert sub.is_lifetime is False
    assert sub.expires_at is not None
    assert sub.source == "payment"
    assert await has_active_subscription(session, user_id) is True


@pytest.mark.asyncio
async def test_activate_lifetime(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    plan = await _create_plan(session, is_lifetime=True)

    sub = await activate_subscription(session, user_id, plan.id)
    assert sub.is_active is True
    assert sub.is_lifetime is True
    assert sub.expires_at is None
    assert await has_active_subscription(session, user_id) is True


@pytest.mark.asyncio
async def test_extend_subscription(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    plan = await _create_plan(session, duration_months=1)

    sub1 = await activate_subscription(session, user_id, plan.id)
    original_expires = sub1.expires_at
    sub2 = await activate_subscription(session, user_id, plan.id)
    assert sub2.id == sub1.id
    assert sub2.expires_at > original_expires


@pytest.mark.asyncio
async def test_lifetime_overwrites_monthly(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    monthly = await _create_plan(session, duration_months=1)
    lifetime = await _create_plan(session, is_lifetime=True)

    await activate_subscription(session, user_id, monthly.id)
    sub = await activate_subscription(session, user_id, lifetime.id)
    assert sub.is_lifetime is True


@pytest.mark.asyncio
async def test_lifetime_ignores_monthly(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    lifetime = await _create_plan(session, is_lifetime=True)
    monthly = await _create_plan(session, duration_months=1)

    await activate_subscription(session, user_id, lifetime.id)
    sub = await activate_subscription(session, user_id, monthly.id)
    assert sub.is_lifetime is True


@pytest.mark.asyncio
async def test_grant_subscription_months(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    sub = await grant_subscription(session, user_id, months=3, source="admin")
    assert sub.is_active is True
    assert sub.is_lifetime is False
    assert sub.expires_at is not None
    assert sub.plan_id is None


@pytest.mark.asyncio
async def test_grant_subscription_lifetime(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    sub = await grant_subscription(session, user_id, is_lifetime=True, source="admin")
    assert sub.is_active is True
    assert sub.is_lifetime is True


@pytest.mark.asyncio
async def test_grant_extends_existing(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    sub1 = await grant_subscription(session, user_id, months=1, source="admin")
    original_expires = sub1.expires_at
    sub2 = await grant_subscription(session, user_id, months=2, source="referral")
    assert sub2.id == sub1.id
    assert sub2.expires_at > original_expires


@pytest.mark.asyncio
async def test_grant_invalid_months(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    with pytest.raises(ValueError):
        await grant_subscription(session, user_id, months=0)


@pytest.mark.asyncio
async def test_deactivate_expired(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    now = datetime.now(UTC)
    from dateutil.relativedelta import relativedelta

    expired = Subscription(
        user_id=user_id,
        starts_at=now - relativedelta(months=2),
        expires_at=now - relativedelta(days=1),
        is_active=True,
        is_lifetime=False,
        source="payment",
    )
    session.add(expired)
    await session.flush()

    count = await deactivate_expired_subscriptions(session)
    assert count == 1
    await session.refresh(expired)
    assert expired.is_active is False


@pytest.mark.asyncio
async def test_deactivate_skips_lifetime(session: AsyncSession, user_id: int):
    await _create_test_user(session, user_id)
    lifetime = Subscription(
        user_id=user_id,
        starts_at=datetime.now(UTC),
        is_active=True,
        is_lifetime=True,
        source="admin",
    )
    session.add(lifetime)
    await session.flush()

    count = await deactivate_expired_subscriptions(session)
    assert count == 0


@pytest.mark.asyncio
async def test_get_subscription_plans(session: AsyncSession):
    plan1 = SubscriptionPlan(
        name_ru="A", name_en="A", price_stars=50, sort_order=2, is_active=True
    )
    plan2 = SubscriptionPlan(
        name_ru="B", name_en="B", price_stars=100, sort_order=1, is_active=True
    )
    plan3 = SubscriptionPlan(name_ru="C", name_en="C", price_stars=200, is_active=False)
    session.add_all([plan1, plan2, plan3])
    await session.flush()

    plans = await get_subscription_plans(session)
    assert len(plans) == 2
    assert plans[0].name_en == "B"
    assert plans[1].name_en == "A"
