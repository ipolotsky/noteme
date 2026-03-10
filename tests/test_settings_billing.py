import sys
import types
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

_bot_module = types.ModuleType("app.bot")
_bot_module.bot = MagicMock()
if "app.bot" not in sys.modules:
    sys.modules["app.bot"] = _bot_module


def _make_mock_user(
    user_id: int = 100,
    max_events: int = 10,
    max_wishes: int = 10,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.language = "ru"
    user.timezone = "Europe/Moscow"
    user.spoiler_enabled = False
    user.notifications_enabled = True
    user.notify_day_before = True
    user.notify_week_before = True
    user.notify_weekly_digest = True
    user.weekly_digest_day = 6
    user.weekly_digest_time = MagicMock()
    user.weekly_digest_time.strftime = MagicMock(return_value="19:00")
    user.notify_day_before_time = MagicMock()
    user.notify_day_before_time.strftime = MagicMock(return_value="10:00")
    user.notify_week_before_time = MagicMock()
    user.notify_week_before_time.strftime = MagicMock(return_value="10:00")
    user.max_events = max_events
    user.max_wishes = max_wishes
    user.onboarding_completed = True
    return user


def _mock_callback() -> AsyncMock:
    cb = AsyncMock()
    cb.data = "noop"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.message.chat = MagicMock()
    cb.message.chat.id = 123
    return cb


class TestSettingsBilling:
    async def test_billing_free_tier(self):
        from app.handlers.settings import settings_billing

        cb = _mock_callback()
        user = _make_mock_user(max_events=10, max_wishes=10)
        session = AsyncMock()

        with (
            patch(
                "app.services.subscription_service.get_active_subscription",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                side_effect=lambda s, k, d: d,
            ),
            patch(
                "app.services.event_service.count_user_events",
                new_callable=AsyncMock,
                return_value=3,
            ),
            patch(
                "app.services.wish_service.count_user_wishes",
                new_callable=AsyncMock,
                return_value=5,
            ),
        ):
            await settings_billing(cb, user, "ru", session)

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "3/10" in text
        assert "5/10" in text

    async def test_billing_active_subscription(self):
        from app.handlers.settings import settings_billing

        cb = _mock_callback()
        user = _make_mock_user()
        session = AsyncMock()

        sub = MagicMock()
        sub.is_lifetime = False
        sub.expires_at = datetime(2025, 12, 31, tzinfo=UTC)

        with patch(
            "app.services.subscription_service.get_active_subscription",
            new_callable=AsyncMock,
            return_value=sub,
        ):
            await settings_billing(cb, user, "ru", session)

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "31.12.2025" in text

    async def test_billing_lifetime(self):
        from app.handlers.settings import settings_billing

        cb = _mock_callback()
        user = _make_mock_user()
        session = AsyncMock()

        sub = MagicMock()
        sub.is_lifetime = True
        sub.expires_at = None

        with patch(
            "app.services.subscription_service.get_active_subscription",
            new_callable=AsyncMock,
            return_value=sub,
        ):
            await settings_billing(cb, user, "ru", session)

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "навсегда" in text.lower()

    async def test_billing_free_has_choose_plan_button(self):
        from app.handlers.settings import settings_billing

        cb = _mock_callback()
        user = _make_mock_user()
        session = AsyncMock()

        with (
            patch(
                "app.services.subscription_service.get_active_subscription",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                side_effect=lambda s, k, d: d,
            ),
            patch(
                "app.services.event_service.count_user_events",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "app.services.wish_service.count_user_wishes",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            await settings_billing(cb, user, "ru", session)

        kb = cb.message.edit_text.call_args[1]["reply_markup"]
        button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("тариф" in x.lower() for x in button_texts)

    async def test_billing_lifetime_no_plan_button(self):
        from app.handlers.settings import settings_billing

        cb = _mock_callback()
        user = _make_mock_user()
        session = AsyncMock()

        sub = MagicMock()
        sub.is_lifetime = True

        with patch(
            "app.services.subscription_service.get_active_subscription",
            new_callable=AsyncMock,
            return_value=sub,
        ):
            await settings_billing(cb, user, "ru", session)

        kb = cb.message.edit_text.call_args[1]["reply_markup"]
        button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert not any("тариф" in x.lower() for x in button_texts)


class TestSettingsReferral:
    async def test_referral_shows_link_and_stats(self):
        from app.handlers.settings import settings_referral

        cb = _mock_callback()
        user = _make_mock_user()
        session = AsyncMock()

        with (
            patch("app.config.settings", MagicMock(bot_username="test_bot")),
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "app.services.referral_service.get_referral_link",
                return_value="https://t.me/test_bot?start=ref_100",
            ),
            patch(
                "app.services.referral_service.get_referral_stats",
                new_callable=AsyncMock,
                return_value={"referral_count": 3},
            ),
        ):
            await settings_referral(cb, user, "ru", session)

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "t.me/test_bot?start=ref_100" in text
        assert "3" in text

    async def test_referral_has_back_button(self):
        from app.handlers.settings import settings_referral

        cb = _mock_callback()
        user = _make_mock_user()
        session = AsyncMock()

        with (
            patch("app.config.settings", MagicMock(bot_username="test_bot")),
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "app.services.referral_service.get_referral_link",
                return_value="https://t.me/test_bot?start=ref_100",
            ),
            patch(
                "app.services.referral_service.get_referral_stats",
                new_callable=AsyncMock,
                return_value={"referral_count": 0},
            ),
        ):
            await settings_referral(cb, user, "ru", session)

        kb = cb.message.edit_text.call_args[1]["reply_markup"]
        button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("Назад" in x for x in button_texts)


class TestSettingsKeyboard:
    def test_settings_kb_has_billing_button(self):
        from app.keyboards.settings import settings_kb

        user = _make_mock_user()
        kb = settings_kb(user, "ru")
        button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("Подписка" in x for x in button_texts)

    def test_settings_kb_has_referral_button(self):
        from app.keyboards.settings import settings_kb

        user = _make_mock_user()
        kb = settings_kb(user, "ru")
        button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("друга" in x.lower() for x in button_texts)

    def test_billing_kb_free_has_plan_button(self):
        from app.keyboards.settings import billing_kb

        kb = billing_kb("ru", has_subscription=False, is_lifetime=False)
        button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert len(button_texts) == 2
        assert any("тариф" in x.lower() for x in button_texts)
        assert any("Назад" in x for x in button_texts)

    def test_billing_kb_lifetime_no_plan_button(self):
        from app.keyboards.settings import billing_kb

        kb = billing_kb("ru", has_subscription=True, is_lifetime=True)
        button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert len(button_texts) == 1
        assert "Назад" in button_texts[0]

    def test_billing_kb_active_has_plan_button(self):
        from app.keyboards.settings import billing_kb

        kb = billing_kb("ru", has_subscription=True, is_lifetime=False)
        button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert len(button_texts) == 2
        assert any("тариф" in x.lower() for x in button_texts)
