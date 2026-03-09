"""App settings service — DB-backed key-value config with Redis cache."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings
from app.services.cache import _get_redis

logger = logging.getLogger(__name__)

SETTINGS_CACHE_TTL = 300
SETTINGS_CACHE_PREFIX = "app_setting:"


async def get_setting(
    session: AsyncSession, key: str, default: str | None = None
) -> str | None:
    try:
        r = _get_redis()
        cached = await r.get(f"{SETTINGS_CACHE_PREFIX}{key}")
        if cached is not None:
            return cached
    except Exception:
        pass

    result = await session.execute(
        select(AppSettings.value).where(AppSettings.key == key)
    )
    value = result.scalar_one_or_none()
    if value is None:
        return default

    try:
        r = _get_redis()
        await r.set(f"{SETTINGS_CACHE_PREFIX}{key}", value, ex=SETTINGS_CACHE_TTL)
    except Exception:
        pass

    return value


async def get_int_setting(
    session: AsyncSession, key: str, default: int = 0
) -> int:
    value = await get_setting(session, key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


async def set_setting(
    session: AsyncSession, key: str, value: str, description: str | None = None
) -> None:
    result = await session.execute(
        select(AppSettings).where(AppSettings.key == key)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.value = value
        if description is not None:
            existing.description = description
    else:
        session.add(AppSettings(key=key, value=value, description=description))
    await session.flush()

    try:
        r = _get_redis()
        await r.set(f"{SETTINGS_CACHE_PREFIX}{key}", value, ex=SETTINGS_CACHE_TTL)
    except Exception:
        pass
