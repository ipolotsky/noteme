"""Tests for free tier limit restrictions."""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_bot_module = types.ModuleType("app.bot")
_bot_module.bot = MagicMock()
if "app.bot" not in sys.modules:
    sys.modules["app.bot"] = _bot_module


def _make_mock_user(
    user_id: int = 100,
    is_active: bool = True,
    notifications_enabled: bool = True,
    notify_day_before: bool = True,
    language: str = "ru",
    max_events: int = 10,
    max_wishes: int = 10,
    spoiler_enabled: bool = False,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.is_active = is_active
    user.notifications_enabled = notifications_enabled
    user.notify_day_before = notify_day_before
    user.language = language
    user.max_events = max_events
    user.max_wishes = max_wishes
    user.spoiler_enabled = spoiler_enabled
    return user


class TestIsOverFreeLimit:
    async def test_with_active_subscription(self):
        from app.services.subscription_service import is_over_free_limit

        session = AsyncMock()
        with patch(
            "app.services.subscription_service.has_active_subscription",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await is_over_free_limit(session, 100)

        assert result is False

    async def test_no_sub_events_over_limit(self):
        from app.services.subscription_service import is_over_free_limit

        user = _make_mock_user(max_events=5, max_wishes=10)
        session = AsyncMock()
        session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.has_active_subscription",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.event_service.count_user_events",
                new_callable=AsyncMock,
                return_value=6,
            ),
            patch(
                "app.services.wish_service.count_user_wishes",
                new_callable=AsyncMock,
                return_value=3,
            ),
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                side_effect=lambda session, key, default: default,
            ),
        ):
            result = await is_over_free_limit(session, 100)

        assert result is True

    async def test_no_sub_wishes_over_limit(self):
        from app.services.subscription_service import is_over_free_limit

        user = _make_mock_user(max_events=10, max_wishes=5)
        session = AsyncMock()
        session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.has_active_subscription",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.event_service.count_user_events",
                new_callable=AsyncMock,
                return_value=3,
            ),
            patch(
                "app.services.wish_service.count_user_wishes",
                new_callable=AsyncMock,
                return_value=6,
            ),
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                side_effect=lambda session, key, default: default,
            ),
        ):
            result = await is_over_free_limit(session, 100)

        assert result is True

    async def test_no_sub_at_exact_limit(self):
        from app.services.subscription_service import is_over_free_limit

        user = _make_mock_user(max_events=5, max_wishes=5)
        session = AsyncMock()
        session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.has_active_subscription",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.event_service.count_user_events",
                new_callable=AsyncMock,
                return_value=5,
            ),
            patch(
                "app.services.wish_service.count_user_wishes",
                new_callable=AsyncMock,
                return_value=5,
            ),
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                side_effect=lambda session, key, default: default,
            ),
        ):
            result = await is_over_free_limit(session, 100)

        assert result is False

    async def test_no_sub_under_limits(self):
        from app.services.subscription_service import is_over_free_limit

        user = _make_mock_user(max_events=10, max_wishes=10)
        session = AsyncMock()
        session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.has_active_subscription",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.event_service.count_user_events",
                new_callable=AsyncMock,
                return_value=3,
            ),
            patch(
                "app.services.wish_service.count_user_wishes",
                new_callable=AsyncMock,
                return_value=2,
            ),
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                side_effect=lambda session, key, default: default,
            ),
        ):
            result = await is_over_free_limit(session, 100)

        assert result is False

    async def test_nonexistent_user(self):
        from app.services.subscription_service import is_over_free_limit

        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        with patch(
            "app.services.subscription_service.has_active_subscription",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await is_over_free_limit(session, 999)

        assert result is False


class TestNotificationTeaser:
    @pytest.fixture(autouse=True)
    def setup_patches(self):
        self.mock_bot = AsyncMock()
        self.mock_session = AsyncMock()
        self.mock_session_ctx = AsyncMock()
        self.mock_session_ctx.__aenter__ = AsyncMock(return_value=self.mock_session)
        self.mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        self.patches = [
            patch(
                "app.workers.notifications.async_session_factory",
                return_value=self.mock_session_ctx,
            ),
            patch("app.bot.bot", self.mock_bot),
        ]
        for p in self.patches:
            p.start()
        yield
        for p in self.patches:
            p.stop()

    async def test_day_before_sends_teaser_when_over_limit(self):
        from app.workers.notifications import send_day_before_notification

        user = _make_mock_user()
        self.mock_session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.is_over_free_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.workers.notifications.get_dates_for_day",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "app.workers.notifications.has_notification_been_sent",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("app.workers.notifications.log_notification", new_callable=AsyncMock),
        ):
            result = await send_day_before_notification({}, 100)

        assert result is True
        self.mock_bot.send_message.assert_called_once()
        call_args = self.mock_bot.send_message.call_args
        assert call_args.args[0] == 100

    async def test_day_before_skips_teaser_when_no_dates(self):
        from app.workers.notifications import send_day_before_notification

        user = _make_mock_user()
        self.mock_session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.is_over_free_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.workers.notifications.get_dates_for_day",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await send_day_before_notification({}, 100)

        assert result is False
        self.mock_bot.send_message.assert_not_called()

    async def test_day_before_normal_flow_when_under_limit(self):
        from app.workers.notifications import send_day_before_notification

        user = _make_mock_user()
        self.mock_session.get = AsyncMock(return_value=user)
        mock_bd = MagicMock()

        with (
            patch(
                "app.services.subscription_service.is_over_free_limit",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.workers.notifications.get_dates_for_day",
                new_callable=AsyncMock,
                return_value=[mock_bd],
            ),
            patch(
                "app.workers.notifications._send_date_card",
                new_callable=AsyncMock,
            ) as mock_card,
            patch("app.workers.notifications.log_notification", new_callable=AsyncMock),
        ):
            result = await send_day_before_notification({}, 100)

        assert result is True
        assert self.mock_bot.send_message.call_count == 1
        mock_card.assert_called_once()

    async def test_teaser_dedup_skips_if_already_sent(self):
        from app.workers.notifications import send_day_before_notification

        user = _make_mock_user()
        self.mock_session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.is_over_free_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.workers.notifications.get_dates_for_day",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "app.workers.notifications.has_notification_been_sent",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await send_day_before_notification({}, 100)

        assert result is False
        self.mock_bot.send_message.assert_not_called()

    async def test_week_before_sends_teaser_when_over_limit(self):
        from app.workers.notifications import send_week_before_notification

        user = _make_mock_user()
        user.notify_week_before = True
        self.mock_session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.is_over_free_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.workers.notifications.get_dates_for_day",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "app.workers.notifications.has_notification_been_sent",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("app.workers.notifications.log_notification", new_callable=AsyncMock),
        ):
            result = await send_week_before_notification({}, 100)

        assert result is True
        self.mock_bot.send_message.assert_called_once()

    async def test_weekly_digest_sends_teaser_when_over_limit(self):
        from app.workers.notifications import send_weekly_digest_notification

        user = _make_mock_user()
        user.notify_weekly_digest = True
        self.mock_session.get = AsyncMock(return_value=user)

        with (
            patch(
                "app.services.subscription_service.is_over_free_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.workers.notifications.get_dates_for_range",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "app.workers.notifications.has_notification_been_sent",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("app.workers.notifications.log_notification", new_callable=AsyncMock),
        ):
            result = await send_weekly_digest_notification({}, 100)

        assert result is True
        self.mock_bot.send_message.assert_called_once()
