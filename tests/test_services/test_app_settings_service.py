"""Tests for app settings service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings
from app.services.app_settings_service import get_int_setting, get_setting, set_setting


@pytest.mark.asyncio
async def test_get_setting_default(session: AsyncSession):
    value = await get_setting(session, "nonexistent", "fallback")
    assert value == "fallback"


@pytest.mark.asyncio
async def test_get_setting_none_default(session: AsyncSession):
    value = await get_setting(session, "nonexistent")
    assert value is None


@pytest.mark.asyncio
async def test_set_and_get_setting(session: AsyncSession):
    await set_setting(session, "test_key", "test_value", "A test setting")
    value = await get_setting(session, "test_key")
    assert value == "test_value"


@pytest.mark.asyncio
async def test_update_setting(session: AsyncSession):
    await set_setting(session, "key", "v1")
    await set_setting(session, "key", "v2")
    value = await get_setting(session, "key")
    assert value == "v2"


@pytest.mark.asyncio
async def test_get_int_setting(session: AsyncSession):
    session.add(AppSettings(key="max_items", value="42"))
    await session.flush()
    value = await get_int_setting(session, "max_items", 0)
    assert value == 42


@pytest.mark.asyncio
async def test_get_int_setting_default(session: AsyncSession):
    value = await get_int_setting(session, "missing", 99)
    assert value == 99


@pytest.mark.asyncio
async def test_get_int_setting_invalid_value(session: AsyncSession):
    session.add(AppSettings(key="bad_int", value="not_a_number"))
    await session.flush()
    value = await get_int_setting(session, "bad_int", 10)
    assert value == 10
