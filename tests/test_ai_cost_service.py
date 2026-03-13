import sys
import types
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_bot_module = types.ModuleType("app.bot")
_bot_module.bot = AsyncMock()
if "app.bot" not in sys.modules:
    sys.modules["app.bot"] = _bot_module

from app.services.ai_cost_service import (  # noqa: E402
    MODEL_PRICING,
    STARS_PER_USD,
    calculate_cost_usd,
    get_current_month_stats,
    get_exchange_rates,
    get_monthly_stats,
    get_users_token_stats,
)


class TestCalculateCostUsd:
    def test_known_model(self):
        cost = calculate_cost_usd(1_000_000, 1_000_000, "gpt-4o-mini")
        expected = MODEL_PRICING["gpt-4o-mini"]["input"] + MODEL_PRICING["gpt-4o-mini"]["output"]
        assert abs(cost - expected) < 0.0001

    def test_unknown_model(self):
        assert calculate_cost_usd(1000, 500, "unknown-model") == 0.0

    def test_zero_tokens(self):
        assert calculate_cost_usd(0, 0, "gpt-4o-mini") == 0.0

    def test_prompt_only(self):
        cost = calculate_cost_usd(500_000, 0, "gpt-4o-mini")
        expected = (500_000 / 1_000_000) * MODEL_PRICING["gpt-4o-mini"]["input"]
        assert abs(cost - expected) < 0.0001

    def test_completion_only(self):
        cost = calculate_cost_usd(0, 200_000, "gpt-4o-mini")
        expected = (200_000 / 1_000_000) * MODEL_PRICING["gpt-4o-mini"]["output"]
        assert abs(cost - expected) < 0.0001

    def test_gpt4o_pricing(self):
        cost = calculate_cost_usd(1_000_000, 1_000_000, "gpt-4o")
        expected = MODEL_PRICING["gpt-4o"]["input"] + MODEL_PRICING["gpt-4o"]["output"]
        assert abs(cost - expected) < 0.0001


class TestGetExchangeRates:
    @pytest.mark.asyncio
    async def test_returns_rates_on_success(self):
        import app.services.ai_cost_service as svc

        svc._rates_cache = None
        svc._rates_cache_time = 0

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"the-open-network": {"usd": 2.5}}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_client
        mock_cm.__aexit__.return_value = False

        with patch(
            "app.services.ai_cost_service.httpx.AsyncClient", return_value=mock_cm
        ):
            rates = await get_exchange_rates()

        assert abs(rates["ton_per_usd"] - 0.4) < 0.0001
        assert rates["stars_per_usd"] == STARS_PER_USD

    @pytest.mark.asyncio
    async def test_returns_cached_rates(self):
        import time

        import app.services.ai_cost_service as svc

        svc._rates_cache = {"ton_per_usd": 0.5, "stars_per_usd": STARS_PER_USD}
        svc._rates_cache_time = time.monotonic()

        rates = await get_exchange_rates()
        assert rates["ton_per_usd"] == 0.5

    @pytest.mark.asyncio
    async def test_handles_api_failure(self):
        import app.services.ai_cost_service as svc

        svc._rates_cache = None
        svc._rates_cache_time = 0

        with patch(
            "app.services.ai_cost_service.httpx.AsyncClient",
            side_effect=Exception("connection error"),
        ):
            rates = await get_exchange_rates()

        assert rates["ton_per_usd"] == 0.0
        assert rates["stars_per_usd"] == STARS_PER_USD


class TestGetUsersTokenStats:
    @pytest.mark.asyncio
    async def test_empty_db(self, session):
        users, total = await get_users_token_stats(session)
        assert total == 0
        assert users == []

    @pytest.mark.asyncio
    async def test_with_data(self, session):
        from app.models.ai_log import AILog
        from app.models.user import User

        user = User(id=111, language="en", first_name="Test")
        session.add(user)
        await session.flush()

        now = datetime.now(UTC)
        for i in range(3):
            session.add(
                AILog(
                    user_id=111,
                    agent_name="router",
                    model="gpt-4o-mini",
                    tokens_prompt=100,
                    tokens_completion=50,
                    tokens_total=150,
                    created_at=now - timedelta(days=i),
                )
            )
        await session.commit()

        users, total = await get_users_token_stats(session)
        assert total == 1
        assert len(users) == 1
        assert users[0]["user_id"] == 111
        assert users[0]["tokens_total"] == 450
        assert users[0]["tokens_prompt"] == 300
        assert users[0]["tokens_completion"] == 150
        assert users[0]["cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_pagination(self, session):
        from app.models.ai_log import AILog
        from app.models.user import User

        for uid in range(1, 4):
            session.add(User(id=uid, language="en", first_name=f"User{uid}"))
        await session.flush()

        now = datetime.now(UTC)
        for uid in range(1, 4):
            session.add(
                AILog(
                    user_id=uid,
                    agent_name="router",
                    model="gpt-4o-mini",
                    tokens_prompt=uid * 100,
                    tokens_completion=uid * 50,
                    tokens_total=uid * 150,
                    created_at=now,
                )
            )
        await session.commit()

        page1, total = await get_users_token_stats(session, page=1, page_size=2)
        assert total == 3
        assert len(page1) == 2

        page2, total2 = await get_users_token_stats(session, page=2, page_size=2)
        assert total2 == 3
        assert len(page2) == 1


class TestGetMonthlyStats:
    @pytest.mark.asyncio
    async def test_empty_db(self, session):
        stats = await get_monthly_stats(session)
        assert stats == []

    @pytest.mark.asyncio
    async def test_with_data(self, session):
        from app.models.ai_log import AILog
        from app.models.user import User

        session.add(User(id=222, language="en", first_name="Test"))
        await session.flush()

        now = datetime.now(UTC)
        session.add(
            AILog(
                user_id=222,
                agent_name="event_agent",
                model="gpt-4o-mini",
                tokens_prompt=500,
                tokens_completion=200,
                tokens_total=700,
                created_at=now,
            )
        )
        await session.commit()

        stats = await get_monthly_stats(session, months=1)
        assert len(stats) == 1
        assert stats[0]["tokens_total"] == 700
        assert stats[0]["cost_usd"] > 0
        assert stats[0]["calls"] == 1


class TestGetCurrentMonthStats:
    @pytest.mark.asyncio
    async def test_empty_db(self, session):
        stats = await get_current_month_stats(session)
        assert stats["tokens_total"] == 0
        assert stats["cost_usd"] == 0.0
        assert stats["calls"] == 0

    @pytest.mark.asyncio
    async def test_with_data(self, session):
        from app.models.ai_log import AILog
        from app.models.user import User

        session.add(User(id=333, language="en", first_name="Test"))
        await session.flush()

        now = datetime.now(UTC)
        for _ in range(5):
            session.add(
                AILog(
                    user_id=333,
                    agent_name="validation",
                    model="gpt-4o-mini",
                    tokens_prompt=200,
                    tokens_completion=100,
                    tokens_total=300,
                    created_at=now,
                )
            )
        await session.commit()

        stats = await get_current_month_stats(session)
        assert stats["tokens_total"] == 1500
        assert stats["tokens_prompt"] == 1000
        assert stats["tokens_completion"] == 500
        assert stats["calls"] == 5
        assert stats["cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_multiple_models(self, session):
        from app.models.ai_log import AILog
        from app.models.user import User

        session.add(User(id=444, language="en", first_name="Test"))
        await session.flush()

        now = datetime.now(UTC)
        session.add(
            AILog(
                user_id=444,
                agent_name="router",
                model="gpt-4o-mini",
                tokens_prompt=100,
                tokens_completion=50,
                tokens_total=150,
                created_at=now,
            )
        )
        session.add(
            AILog(
                user_id=444,
                agent_name="event_agent",
                model="gpt-4o",
                tokens_prompt=200,
                tokens_completion=100,
                tokens_total=300,
                created_at=now,
            )
        )
        await session.commit()

        stats = await get_current_month_stats(session)
        assert stats["tokens_total"] == 450
        assert stats["calls"] == 2

        mini_cost = calculate_cost_usd(100, 50, "gpt-4o-mini")
        big_cost = calculate_cost_usd(200, 100, "gpt-4o")
        assert abs(stats["cost_usd"] - (mini_cost + big_cost)) < 0.0001
