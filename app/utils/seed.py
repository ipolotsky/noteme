"""Seed script for beautiful date strategies (16 strategies from spec Appendix A)."""

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.beautiful_date_strategy import BeautifulDateStrategy

STRATEGIES = [
    # 1-8: Round multiples of days
    {
        "name_ru": "Круглые десятки дней",
        "name_en": "Round tens of days",
        "strategy_type": "multiples",
        "params": {"base": 10, "min": 10, "max": 180, "unit": "days"},
        "priority": 1,
    },
    {
        "name_ru": "Круглые сотни дней",
        "name_en": "Round hundreds of days",
        "strategy_type": "multiples",
        "params": {"base": 100, "min": 100, "max": 1000, "unit": "days"},
        "priority": 2,
    },
    {
        "name_ru": "Круглые 500 дней",
        "name_en": "Round 500s of days",
        "strategy_type": "multiples",
        "params": {"base": 500, "min": 500, "max": 10000, "unit": "days"},
        "priority": 3,
    },
    {
        "name_ru": "Круглые тысячи дней",
        "name_en": "Round thousands of days",
        "strategy_type": "multiples",
        "params": {"base": 1000, "min": 1000, "max": 100000, "unit": "days"},
        "priority": 4,
    },
    {
        "name_ru": "Круглые десятки недель",
        "name_en": "Round tens of weeks",
        "strategy_type": "multiples",
        "params": {"base": 10, "min": 10, "max": 520, "unit": "weeks"},
        "priority": 5,
    },
    {
        "name_ru": "Круглые сотни недель",
        "name_en": "Round hundreds of weeks",
        "strategy_type": "multiples",
        "params": {"base": 100, "min": 100, "max": 5200, "unit": "weeks"},
        "priority": 6,
    },
    {
        "name_ru": "Круглые десятки месяцев",
        "name_en": "Round tens of months",
        "strategy_type": "multiples",
        "params": {"base": 10, "min": 10, "max": 120, "unit": "months"},
        "priority": 7,
    },
    {
        "name_ru": "Круглые сотни месяцев",
        "name_en": "Round hundreds of months",
        "strategy_type": "multiples",
        "params": {"base": 100, "min": 100, "max": 1200, "unit": "months"},
        "priority": 8,
    },
    # 9: Repdigits
    {
        "name_ru": "Репдиджиты (одинаковые цифры)",
        "name_en": "Repdigits (same digits)",
        "strategy_type": "repdigits",
        "params": {"exclude": [333, 666], "max_days": 100000, "unit": "days"},
        "priority": 9,
    },
    # 10: Sequences
    {
        "name_ru": "Последовательности",
        "name_en": "Sequences",
        "strategy_type": "sequence",
        "params": {"sequences": [123, 1234, 12345, 123456], "unit": "days"},
        "priority": 10,
    },
    # 11: Special numbers
    {
        "name_ru": "Особые числа",
        "name_en": "Special numbers",
        "strategy_type": "special",
        "params": {"numbers": [69], "unit": "days"},
        "priority": 11,
    },
    # 12: Compound — N days N weeks N months
    {
        "name_ru": "N дней N недель N месяцев",
        "name_en": "N days N weeks N months",
        "strategy_type": "compound",
        "params": {"parts": ["days", "weeks", "months"], "min_n": 1, "max_n": 12},
        "priority": 12,
    },
    # 13: Compound — N days N months N years
    {
        "name_ru": "N дней N месяцев N лет",
        "name_en": "N days N months N years",
        "strategy_type": "compound",
        "params": {"parts": ["days", "months", "years"], "min_n": 1, "max_n": 12},
        "priority": 13,
    },
    # 14: Anniversaries
    {
        "name_ru": "Годовщины",
        "name_en": "Anniversaries",
        "strategy_type": "anniversary",
        "params": {
            "years": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 100]
        },
        "priority": 14,
    },
    # 15: Compound — N weeks N months N years
    {
        "name_ru": "N недель N месяцев N лет",
        "name_en": "N weeks N months N years",
        "strategy_type": "compound",
        "params": {"parts": ["weeks", "months", "years"], "min_n": 1, "max_n": 12},
        "priority": 15,
    },
    # 16: Powers of two
    {
        "name_ru": "Степени двойки",
        "name_en": "Powers of two",
        "strategy_type": "powers_of_two",
        "params": {"min_power": 8, "max_power": 20, "units": ["days", "weeks"]},
        "priority": 16,
    },
]


async def seed_strategies() -> int:
    """Seed beautiful date strategies. Returns number of strategies created."""
    created = 0
    async with async_session_factory() as session:
        for data in STRATEGIES:
            existing = await session.execute(
                select(BeautifulDateStrategy).where(
                    BeautifulDateStrategy.name_en == data["name_en"]
                )
            )
            if existing.scalar_one_or_none() is None:
                strategy = BeautifulDateStrategy(**data)
                session.add(strategy)
                created += 1
        await session.commit()
    return created


async def main() -> None:
    count = await seed_strategies()
    print(f"Seeded {count} strategies (total expected: {len(STRATEGIES)})")


if __name__ == "__main__":
    asyncio.run(main())
