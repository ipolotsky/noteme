"""Tests for subscription expiry notifications."""

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError


def _make_mock_user(
    user_id: int = 100,
    is_active: bool = True,
    notifications_enabled: bool = True,
    language: str = "ru",
    timezone: str = "Europe/Moscow",
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.is_active = is_active
    user.notifications_enabled = notifications_enabled
    user.language = language
    user.timezone = timezone
    return user


def _make_mock_subscription(
    expires_at: datetime | None = None,
    is_lifetime: bool = False,
    is_active: bool = True,
) -> MagicMock:
    sub = MagicMock()
    sub.expires_at = expires_at or (datetime.now(UTC) + timedelta(days=7))
    sub.is_lifetime = is_lifetime
    sub.is_active = is_active
    return sub


class TestSendSubscriptionExpiryNotification:
    @pytest.fixture(autouse=True)
    def setup_patches(self):
        self.mock_bot = AsyncMock()
        self.mock_session = AsyncMock()
        self.mock_session_ctx = AsyncMock()
        self.mock_session_ctx.__aenter__ = AsyncMock(return_value=self.mock_session)
        self.mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        self.patches = [
            patch("app.workers.notifications.async_session_factory", return_value=self.mock_session_ctx),
            patch("app.bot.bot", self.mock_bot),
        ]
        for p in self.patches:
            p.start()
        yield
        for p in self.patches:
            p.stop()

    async def test_sends_notification_7d(self):
        from app.workers.notifications import send_subscription_expiry_notification

        user = _make_mock_user()
        sub = _make_mock_subscription(expires_at=datetime(2026, 3, 16, 12, 0, tzinfo=UTC))
        self.mock_session.get = AsyncMock(return_value=user)

        with (
            patch("app.services.subscription_service.get_active_subscription", new_callable=AsyncMock, return_value=sub),
            patch("app.workers.notifications.has_notification_been_sent", new_callable=AsyncMock, return_value=False),
            patch("app.workers.notifications.log_notification", new_callable=AsyncMock) as mock_log,
        ):
            result = await send_subscription_expiry_notification({}, 100, 7)

        assert result is True
        self.mock_bot.send_message.assert_called_once()
        call_args = self.mock_bot.send_message.call_args
        assert "7" in call_args.args[1]
        assert "16.03.2026" in call_args.args[1]
        mock_log.assert_called_once()

    async def test_sends_notification_1d(self):
        from app.workers.notifications import send_subscription_expiry_notification

        user = _make_mock_user(language="en")
        sub = _make_mock_subscription(expires_at=datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
        self.mock_session.get = AsyncMock(return_value=user)

        with (
            patch("app.services.subscription_service.get_active_subscription", new_callable=AsyncMock, return_value=sub),
            patch("app.workers.notifications.has_notification_been_sent", new_callable=AsyncMock, return_value=False),
            patch("app.workers.notifications.log_notification", new_callable=AsyncMock),
        ):
            result = await send_subscription_expiry_notification({}, 100, 1)

        assert result is True
        call_args = self.mock_bot.send_message.call_args
        assert "tomorrow" in call_args.args[1].lower()

    async def test_skips_inactive_user(self):
        from app.workers.notifications import send_subscription_expiry_notification

        user = _make_mock_user(is_active=False)
        self.mock_session.get = AsyncMock(return_value=user)

        result = await send_subscription_expiry_notification({}, 100, 7)
        assert result is False
        self.mock_bot.send_message.assert_not_called()

    async def test_skips_notifications_disabled(self):
        from app.workers.notifications import send_subscription_expiry_notification

        user = _make_mock_user(notifications_enabled=False)
        self.mock_session.get = AsyncMock(return_value=user)

        result = await send_subscription_expiry_notification({}, 100, 7)
        assert result is False
        self.mock_bot.send_message.assert_not_called()

    async def test_skips_lifetime_subscription(self):
        from app.workers.notifications import send_subscription_expiry_notification

        user = _make_mock_user()
        sub = _make_mock_subscription(is_lifetime=True)
        self.mock_session.get = AsyncMock(return_value=user)

        with patch("app.services.subscription_service.get_active_subscription", new_callable=AsyncMock, return_value=sub):
            result = await send_subscription_expiry_notification({}, 100, 7)

        assert result is False
        self.mock_bot.send_message.assert_not_called()

    async def test_skips_no_subscription(self):
        from app.workers.notifications import send_subscription_expiry_notification

        user = _make_mock_user()
        self.mock_session.get = AsyncMock(return_value=user)

        with patch("app.services.subscription_service.get_active_subscription", new_callable=AsyncMock, return_value=None):
            result = await send_subscription_expiry_notification({}, 100, 7)

        assert result is False
        self.mock_bot.send_message.assert_not_called()

    async def test_skips_already_sent(self):
        from app.workers.notifications import send_subscription_expiry_notification

        user = _make_mock_user()
        sub = _make_mock_subscription()
        self.mock_session.get = AsyncMock(return_value=user)

        with (
            patch("app.services.subscription_service.get_active_subscription", new_callable=AsyncMock, return_value=sub),
            patch("app.workers.notifications.has_notification_been_sent", new_callable=AsyncMock, return_value=True),
        ):
            result = await send_subscription_expiry_notification({}, 100, 7)

        assert result is False
        self.mock_bot.send_message.assert_not_called()

    async def test_deactivates_user_on_forbidden(self):
        from app.workers.notifications import send_subscription_expiry_notification

        user = _make_mock_user()
        sub = _make_mock_subscription()
        self.mock_session.get = AsyncMock(return_value=user)
        self.mock_bot.send_message.side_effect = TelegramForbiddenError(method=MagicMock(), message="Forbidden")

        with (
            patch("app.services.subscription_service.get_active_subscription", new_callable=AsyncMock, return_value=sub),
            patch("app.workers.notifications.has_notification_been_sent", new_callable=AsyncMock, return_value=False),
        ):
            result = await send_subscription_expiry_notification({}, 100, 7)

        assert result is False
        assert user.is_active is False
        self.mock_session.commit.assert_called()

    async def test_skips_nonexistent_user(self):
        from app.workers.notifications import send_subscription_expiry_notification

        self.mock_session.get = AsyncMock(return_value=None)

        result = await send_subscription_expiry_notification({}, 999, 7)
        assert result is False


class TestCheckSubscriptionExpiryNotifications:
    async def test_sends_at_correct_time(self):
        from app.workers.notifications import check_subscription_expiry_notifications

        user = _make_mock_user(timezone="UTC")
        sub = _make_mock_subscription()

        now_10am = datetime(2026, 3, 9, 10, 0, 0, tzinfo=UTC)

        with (
            patch("app.workers.notifications.datetime") as mock_dt,
            patch("app.workers.notifications.date") as mock_date,
            patch("app.workers.notifications.async_session_factory") as mock_factory,
            patch(
                "app.services.subscription_service.get_users_with_expiring_subscriptions",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "app.workers.notifications.send_subscription_expiry_notification",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send,
        ):
            mock_dt.now.return_value = now_10am
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mock_date.today.return_value = date(2026, 3, 9)
            mock_get.return_value = [(user, sub)]
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_session_ctx

            result = await check_subscription_expiry_notifications({})

        assert result == 2
        assert mock_send.call_count == 2
        mock_send.assert_any_call({}, 100, 7)
        mock_send.assert_any_call({}, 100, 1)

    async def test_skips_wrong_time(self):
        from app.workers.notifications import check_subscription_expiry_notifications

        user = _make_mock_user(timezone="UTC")
        sub = _make_mock_subscription()

        now_9am = datetime(2026, 3, 9, 9, 0, 0, tzinfo=UTC)

        with (
            patch("app.workers.notifications.datetime") as mock_dt,
            patch("app.workers.notifications.date") as mock_date,
            patch("app.workers.notifications.async_session_factory") as mock_factory,
            patch(
                "app.services.subscription_service.get_users_with_expiring_subscriptions",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "app.workers.notifications.send_subscription_expiry_notification",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_dt.now.return_value = now_9am
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mock_date.today.return_value = date(2026, 3, 9)
            mock_get.return_value = [(user, sub)]
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_session_ctx

            result = await check_subscription_expiry_notifications({})

        assert result == 0
        mock_send.assert_not_called()

    async def test_skips_invalid_timezone(self):
        from app.workers.notifications import check_subscription_expiry_notifications

        user = _make_mock_user(timezone="Invalid/Zone")
        sub = _make_mock_subscription()

        now_10am = datetime(2026, 3, 9, 10, 0, 0, tzinfo=UTC)

        with (
            patch("app.workers.notifications.datetime") as mock_dt,
            patch("app.workers.notifications.date") as mock_date,
            patch("app.workers.notifications.async_session_factory") as mock_factory,
            patch(
                "app.services.subscription_service.get_users_with_expiring_subscriptions",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "app.workers.notifications.send_subscription_expiry_notification",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_dt.now.return_value = now_10am
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mock_date.today.return_value = date(2026, 3, 9)
            mock_get.return_value = [(user, sub)]
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_session_ctx

            result = await check_subscription_expiry_notifications({})

        assert result == 0
        mock_send.assert_not_called()

    async def test_no_expiring_subscriptions(self):
        from app.workers.notifications import check_subscription_expiry_notifications

        now_10am = datetime(2026, 3, 9, 10, 0, 0, tzinfo=UTC)

        with (
            patch("app.workers.notifications.datetime") as mock_dt,
            patch("app.workers.notifications.date") as mock_date,
            patch("app.workers.notifications.async_session_factory") as mock_factory,
            patch(
                "app.services.subscription_service.get_users_with_expiring_subscriptions",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.workers.notifications.send_subscription_expiry_notification",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_dt.now.return_value = now_10am
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mock_date.today.return_value = date(2026, 3, 9)
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_session_ctx

            result = await check_subscription_expiry_notifications({})

        assert result == 0
        mock_send.assert_not_called()
