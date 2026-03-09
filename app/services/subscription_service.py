"""Subscription service — activation, validation, expiration."""

import logging
import uuid
from datetime import UTC, date, datetime

from dateutil.relativedelta import relativedelta
from sqlalchemy import Date, cast, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User

logger = logging.getLogger(__name__)


async def has_active_subscription(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(
        select(Subscription.id)
        .where(
            Subscription.user_id == user_id,
            Subscription.is_active.is_(True),
            or_(
                Subscription.is_lifetime.is_(True),
                Subscription.expires_at > func.now(),
            ),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_active_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.is_active.is_(True),
            or_(
                Subscription.is_lifetime.is_(True),
                Subscription.expires_at > func.now(),
            ),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def activate_subscription(
    session: AsyncSession,
    user_id: int,
    plan_id: uuid.UUID,
    source: str = "payment",
) -> Subscription:
    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise ValueError("Plan not found")

    now = datetime.now(UTC)

    if plan.is_lifetime:
        existing = await get_active_subscription(session, user_id)
        if existing is not None and existing.is_lifetime:
            return existing

        if existing is not None:
            existing.is_active = False

        subscription = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            starts_at=now,
            expires_at=None,
            is_active=True,
            is_lifetime=True,
            source=source,
        )
        session.add(subscription)
        await session.flush()
        return subscription

    existing = await get_active_subscription(session, user_id)
    if existing is not None and not existing.is_lifetime:
        base = existing.expires_at if existing.expires_at and existing.expires_at > now else now
        existing.expires_at = base + relativedelta(months=plan.duration_months)
        existing.plan_id = plan_id
        await session.flush()
        return existing

    if existing is not None and existing.is_lifetime:
        return existing

    subscription = Subscription(
        user_id=user_id,
        plan_id=plan_id,
        starts_at=now,
        expires_at=now + relativedelta(months=plan.duration_months),
        is_active=True,
        is_lifetime=False,
        source=source,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def grant_subscription(
    session: AsyncSession,
    user_id: int,
    months: int | None = None,
    is_lifetime: bool = False,
    source: str = "admin",
) -> Subscription:
    now = datetime.now(UTC)

    if is_lifetime:
        existing = await get_active_subscription(session, user_id)
        if existing is not None and existing.is_lifetime:
            return existing

        if existing is not None:
            existing.is_active = False

        subscription = Subscription(
            user_id=user_id,
            plan_id=None,
            starts_at=now,
            expires_at=None,
            is_active=True,
            is_lifetime=True,
            source=source,
        )
        session.add(subscription)
        await session.flush()
        return subscription

    if months is None or months <= 0:
        raise ValueError("months must be positive for non-lifetime subscription")

    existing = await get_active_subscription(session, user_id)
    if existing is not None and existing.is_lifetime:
        return existing

    if existing is not None:
        base = existing.expires_at if existing.expires_at and existing.expires_at > now else now
        existing.expires_at = base + relativedelta(months=months)
        await session.flush()
        return existing

    subscription = Subscription(
        user_id=user_id,
        plan_id=None,
        starts_at=now,
        expires_at=now + relativedelta(months=months),
        is_active=True,
        is_lifetime=False,
        source=source,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def deactivate_expired_subscriptions(session: AsyncSession) -> int:
    result = await session.execute(
        update(Subscription)
        .where(
            Subscription.is_active.is_(True),
            Subscription.is_lifetime.is_(False),
            Subscription.expires_at <= func.now(),
        )
        .values(is_active=False)
    )
    return result.rowcount


async def get_users_with_expiring_subscriptions(
    session: AsyncSession, target_date: date
) -> list[tuple[User, Subscription]]:
    result = await session.execute(
        select(User, Subscription)
        .join(Subscription, Subscription.user_id == User.id)
        .where(
            Subscription.is_active.is_(True),
            Subscription.is_lifetime.is_(False),
            cast(Subscription.expires_at, Date) == target_date,
            User.is_active.is_(True),
            User.notifications_enabled.is_(True),
        )
    )
    return list(result.tuples().all())


async def get_subscription_plans(session: AsyncSession) -> list[SubscriptionPlan]:
    result = await session.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.sort_order)
    )
    return list(result.scalars().all())
