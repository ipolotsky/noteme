"""Referral program service."""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral_reward import ReferralReward

logger = logging.getLogger(__name__)


async def process_referral(
    session: AsyncSession, referrer_id: int, referred_id: int
) -> bool:
    """Grant referral bonus to referrer. Returns True if bonus was granted."""
    from app.services.app_settings_service import get_int_setting
    from app.services.subscription_service import grant_subscription

    existing = await session.execute(
        select(ReferralReward).where(ReferralReward.referred_id == referred_id)
    )
    if existing.scalar_one_or_none() is not None:
        return False

    reward_months = await get_int_setting(session, "referral_reward_months", 1)

    reward = ReferralReward(
        referrer_id=referrer_id,
        referred_id=referred_id,
        reward_months=reward_months,
    )
    session.add(reward)

    await grant_subscription(
        session, referrer_id, months=reward_months, source="referral"
    )

    logger.info(
        "Referral bonus: %d months to user %d (referred %d)",
        reward_months, referrer_id, referred_id,
    )
    return True


def get_referral_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


async def get_referral_stats(session: AsyncSession, user_id: int) -> dict:
    result = await session.execute(
        select(func.count())
        .select_from(ReferralReward)
        .where(ReferralReward.referrer_id == user_id)
    )
    count = result.scalar_one()
    return {"referral_count": count}
