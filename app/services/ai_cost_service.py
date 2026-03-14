import logging
import time

import httpx
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_log import AILog

logger = logging.getLogger(__name__)

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

STARS_PER_USD = 50.0

_rates_cache: dict[str, float] | None = None
_rates_cache_time: float = 0
_RATES_TTL = 900


async def get_exchange_rates() -> dict[str, float]:
    global _rates_cache, _rates_cache_time

    now = time.monotonic()
    if _rates_cache is not None and (now - _rates_cache_time) < _RATES_TTL:
        return _rates_cache

    ton_per_usd = 0.0
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "the-open-network", "vs_currencies": "usd"},
            )
            if response.status_code == 200:
                data = response.json()
                usd_per_ton = data.get("the-open-network", {}).get("usd", 0)
                if usd_per_ton > 0:
                    ton_per_usd = 1.0 / usd_per_ton
    except Exception:
        logger.warning("Failed to fetch TON/USD rate from CoinGecko")

    _rates_cache = {"ton_per_usd": ton_per_usd, "stars_per_usd": STARS_PER_USD}
    _rates_cache_time = now
    return _rates_cache


def calculate_cost_usd(
    tokens_prompt: int,
    tokens_completion: int,
    model: str,
) -> float:
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return 0.0
    return (tokens_prompt / 1_000_000) * pricing["input"] + (
        tokens_completion / 1_000_000
    ) * pricing["output"]


async def get_users_token_stats(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from datetime import UTC, datetime

    from app.models.user import User

    q = (
        select(
            AILog.user_id,
            User.username,
            User.first_name,
            AILog.model,
            func.coalesce(func.sum(AILog.tokens_prompt), 0).label("sum_prompt"),
            func.coalesce(func.sum(AILog.tokens_completion), 0).label("sum_completion"),
            func.coalesce(func.sum(AILog.tokens_total), 0).label("sum_total"),
            func.min(AILog.created_at).label("first_call"),
        )
        .join(User, User.id == AILog.user_id)
        .group_by(AILog.user_id, AILog.model, User.username, User.first_name)
    )

    rows = (await session.execute(q)).all()

    users: dict[int, dict] = {}
    for row in rows:
        uid = row.user_id
        if uid not in users:
            users[uid] = {
                "user_id": uid,
                "username": row.username or row.first_name or str(uid),
                "tokens_prompt": 0,
                "tokens_completion": 0,
                "tokens_total": 0,
                "cost_usd": 0.0,
                "first_call": row.first_call,
            }
        u = users[uid]
        u["tokens_prompt"] += row.sum_prompt
        u["tokens_completion"] += row.sum_completion
        u["tokens_total"] += row.sum_total
        u["cost_usd"] += calculate_cost_usd(row.sum_prompt, row.sum_completion, row.model)
        if row.first_call and (u["first_call"] is None or row.first_call < u["first_call"]):
            u["first_call"] = row.first_call

    now = datetime.now(UTC)
    for u in users.values():
        if u["first_call"]:
            days = max((now - u["first_call"]).days, 1)
            months = max(days / 30.0, 1.0)
            u["avg_monthly_tokens"] = round(u["tokens_total"] / months)
            u["avg_monthly_cost_usd"] = u["cost_usd"] / months
        else:
            u["avg_monthly_tokens"] = u["tokens_total"]
            u["avg_monthly_cost_usd"] = u["cost_usd"]

    sorted_users = sorted(users.values(), key=lambda x: x["tokens_total"], reverse=True)
    total = len(sorted_users)
    offset = (page - 1) * page_size
    paginated = sorted_users[offset : offset + page_size]

    return paginated, total


async def get_monthly_stats(session: AsyncSession, months: int = 6) -> list[dict]:
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=months * 31)

    q = (
        select(
            extract("year", AILog.created_at).label("year"),
            extract("month", AILog.created_at).label("month"),
            AILog.model,
            func.coalesce(func.sum(AILog.tokens_prompt), 0).label("sum_prompt"),
            func.coalesce(func.sum(AILog.tokens_completion), 0).label("sum_completion"),
            func.coalesce(func.sum(AILog.tokens_total), 0).label("sum_total"),
            func.count(AILog.id).label("calls"),
        )
        .where(AILog.created_at >= cutoff)
        .group_by(
            extract("year", AILog.created_at),
            extract("month", AILog.created_at),
            AILog.model,
        )
        .order_by(
            extract("year", AILog.created_at),
            extract("month", AILog.created_at),
        )
    )

    rows = (await session.execute(q)).all()

    monthly: dict[str, dict] = {}
    for row in rows:
        key = f"{int(row.year)}-{int(row.month):02d}"
        if key not in monthly:
            monthly[key] = {
                "month": key,
                "tokens_total": 0,
                "tokens_prompt": 0,
                "tokens_completion": 0,
                "cost_usd": 0.0,
                "calls": 0,
            }
        m = monthly[key]
        m["tokens_total"] += row.sum_total
        m["tokens_prompt"] += row.sum_prompt
        m["tokens_completion"] += row.sum_completion
        m["cost_usd"] += calculate_cost_usd(row.sum_prompt, row.sum_completion, row.model)
        m["calls"] += row.calls

    return sorted(monthly.values(), key=lambda x: x["month"])


async def get_current_month_stats(session: AsyncSession) -> dict:
    from datetime import UTC, datetime

    now = datetime.now(UTC)

    q = (
        select(
            AILog.model,
            func.coalesce(func.sum(AILog.tokens_prompt), 0).label("sum_prompt"),
            func.coalesce(func.sum(AILog.tokens_completion), 0).label("sum_completion"),
            func.coalesce(func.sum(AILog.tokens_total), 0).label("sum_total"),
            func.count(AILog.id).label("calls"),
        )
        .where(
            extract("year", AILog.created_at) == now.year,
            extract("month", AILog.created_at) == now.month,
        )
        .group_by(AILog.model)
    )

    rows = (await session.execute(q)).all()

    result = {
        "tokens_total": 0,
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "cost_usd": 0.0,
        "calls": 0,
    }

    for row in rows:
        result["tokens_total"] += row.sum_total
        result["tokens_prompt"] += row.sum_prompt
        result["tokens_completion"] += row.sum_completion
        result["cost_usd"] += calculate_cost_usd(row.sum_prompt, row.sum_completion, row.model)
        result["calls"] += row.calls

    return result
