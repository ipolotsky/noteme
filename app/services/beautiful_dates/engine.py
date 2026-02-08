"""Strategy engine — registry and recalculation for events."""

import logging
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beautiful_date import BeautifulDate
from app.models.beautiful_date_strategy import BeautifulDateStrategy
from app.models.event import Event
from app.services.beautiful_dates.anniversary import AnniversaryStrategy
from app.services.beautiful_dates.base import BaseStrategy
from app.services.beautiful_dates.compound import CompoundStrategy
from app.services.beautiful_dates.multiples import MultiplesStrategy
from app.services.beautiful_dates.powers_of_two import PowersOfTwoStrategy
from app.services.beautiful_dates.repdigits import RepdigitsStrategy
from app.services.beautiful_dates.sequence import SequenceStrategy
from app.services.beautiful_dates.special import SpecialStrategy

logger = logging.getLogger(__name__)

# Strategy type -> implementation class
_STRATEGY_REGISTRY: dict[str, BaseStrategy] = {
    "multiples": MultiplesStrategy(),
    "repdigits": RepdigitsStrategy(),
    "sequence": SequenceStrategy(),
    "special": SpecialStrategy(),
    "compound": CompoundStrategy(),
    "anniversary": AnniversaryStrategy(),
    "powers_of_two": PowersOfTwoStrategy(),
}


async def get_active_strategies(session: AsyncSession) -> list[BeautifulDateStrategy]:
    """Get all active strategies ordered by priority."""
    result = await session.execute(
        select(BeautifulDateStrategy)
        .where(BeautifulDateStrategy.is_active.is_(True))
        .order_by(BeautifulDateStrategy.priority)
    )
    return list(result.scalars().all())


async def recalculate_for_event(
    session: AsyncSession,
    event: Event,
    strategies: list[BeautifulDateStrategy] | None = None,
) -> int:
    """Recalculate all beautiful dates for a single event.

    Deletes existing beautiful_dates for this event, then generates new ones
    from all active strategies.

    Returns number of beautiful dates created.
    """
    # Delete existing beautiful dates for this event
    await session.execute(
        delete(BeautifulDate).where(BeautifulDate.event_id == event.id)
    )

    if strategies is None:
        strategies = await get_active_strategies(session)

    today = date.today()
    created = 0

    for strategy_model in strategies:
        impl = _STRATEGY_REGISTRY.get(strategy_model.strategy_type)
        if impl is None:
            logger.warning(
                "Unknown strategy type: %s", strategy_model.strategy_type
            )
            continue

        candidates = impl.calculate(
            event.event_date, event.title, strategy_model.params
        )

        for candidate in candidates:
            # Only keep future dates (or today)
            if candidate.target_date < today:
                continue

            bd = BeautifulDate(
                event_id=event.id,
                strategy_id=strategy_model.id,
                target_date=candidate.target_date,
                label_ru=candidate.label_ru,
                label_en=candidate.label_en,
                interval_value=candidate.interval_value,
                interval_unit=candidate.interval_unit,
                compound_parts=candidate.compound_parts,
            )
            session.add(bd)
            created += 1

    await session.flush()
    logger.info(
        "Recalculated %d beautiful dates for event %s (%s)",
        created,
        event.id,
        event.title,
    )
    return created


async def recalculate_for_user(session: AsyncSession, user_id: int) -> int:
    """Recalculate beautiful dates for all events of a user."""
    result = await session.execute(
        select(Event).where(Event.user_id == user_id)
    )
    events = list(result.scalars().all())
    strategies = await get_active_strategies(session)

    total = 0
    for event in events:
        total += await recalculate_for_event(session, event, strategies)
    return total


async def recalculate_all(session: AsyncSession) -> int:
    """Recalculate beautiful dates for ALL events (e.g., after strategy change)."""
    result = await session.execute(select(Event))
    events = list(result.scalars().all())
    strategies = await get_active_strategies(session)

    total = 0
    for event in events:
        total += await recalculate_for_event(session, event, strategies)
    return total
