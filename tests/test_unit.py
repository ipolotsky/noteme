"""Unit tests for keyboards, middlewares, callbacks, schemas, FSM states,
cache, error handler, pagination, config, and metrics.

Each test focuses on a single unit in isolation, mocking external deps.
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import get_or_create_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_user(
    session: AsyncSession,
    user_id: int = 111222333,
    **kwargs,
) -> User:
    defaults = dict(first_name="Test", username="tester")
    defaults.update(kwargs)
    data = UserCreate(id=user_id, **defaults)
    user, _ = await get_or_create_user(session, data)
    return user


def _make_event_obj(**overrides) -> MagicMock:
    """Lightweight mock Event for keyboard functions."""
    ev = MagicMock()
    ev.id = overrides.get("id", uuid.uuid4())
    ev.title = overrides.get("title", "Wedding")
    ev.event_date = overrides.get("event_date", date(2023, 1, 1))
    ev.is_system = overrides.get("is_system", False)
    return ev


def _make_wish_obj(**overrides) -> MagicMock:
    """Lightweight mock Wish for keyboard functions."""
    n = MagicMock()
    n.id = overrides.get("id", uuid.uuid4())
    n.text = overrides.get("text", "Buy headphones")
    n.reminder_date = overrides.get("reminder_date")
    return n


def _make_person_obj(**overrides) -> MagicMock:
    tg = MagicMock()
    tg.id = overrides.get("id", uuid.uuid4())
    tg.name = overrides.get("name", "Family")
    return tg


def _make_bd_obj(**overrides) -> MagicMock:
    bd = MagicMock()
    bd.id = overrides.get("id", uuid.uuid4())
    bd.event_id = overrides.get("event_id", uuid.uuid4())
    bd.label_ru = overrides.get("label_ru", "1000 dney")
    bd.label_en = overrides.get("label_en", "1000 days")
    bd.target_date = overrides.get("target_date", date(2026, 6, 1))
    return bd


# =====================================================================
# CALLBACK DATA FACTORIES
# =====================================================================


class TestCallbackData:
    """Unit tests for callback data pack/unpack roundtrips."""

    def test_menu_cb_pack_unpack(self):
        from app.keyboards.callbacks import MenuCb
        cb = MenuCb(action="feed")
        packed = cb.pack()
        assert "feed" in packed
        unpacked = MenuCb.unpack(packed)
        assert unpacked.action == "feed"

    def test_event_cb_with_defaults(self):
        from app.keyboards.callbacks import EventCb
        cb = EventCb(action="list")
        packed = cb.pack()
        unpacked = EventCb.unpack(packed)
        assert unpacked.action == "list"
        assert unpacked.id == ""
        assert unpacked.page == 0

    def test_event_cb_with_values(self):
        from app.keyboards.callbacks import EventCb
        test_id = str(uuid.uuid4())
        cb = EventCb(action="view", id=test_id, page=3)
        unpacked = EventCb.unpack(cb.pack())
        assert unpacked.id == test_id
        assert unpacked.page == 3

    def test_wish_cb_roundtrip(self):
        from app.keyboards.callbacks import WishCb
        cb = WishCb(action="create")
        assert WishCb.unpack(cb.pack()).action == "create"

    def test_person_cb_roundtrip(self):
        from app.keyboards.callbacks import PersonCb
        cb = PersonCb(action="view", id="abc-123")
        unpacked = PersonCb.unpack(cb.pack())
        assert unpacked.id == "abc-123"

    def test_settings_cb_roundtrip(self):
        from app.keyboards.callbacks import SettingsCb
        cb = SettingsCb(action="timezone", value="Europe/London")
        unpacked = SettingsCb.unpack(cb.pack())
        assert unpacked.value == "Europe/London"

    def test_feed_cb_roundtrip(self):
        from app.keyboards.callbacks import FeedCb
        cb = FeedCb(action="share", id="test-id", page=2)
        unpacked = FeedCb.unpack(cb.pack())
        assert unpacked.action == "share"
        assert unpacked.page == 2

    def test_page_cb_roundtrip(self):
        from app.keyboards.callbacks import PageCb
        cb = PageCb(target="events", page=5)
        unpacked = PageCb.unpack(cb.pack())
        assert unpacked.target == "events"
        assert unpacked.page == 5

    def test_lang_cb_roundtrip(self):
        from app.keyboards.callbacks import LangCb
        cb = LangCb(code="en")
        assert LangCb.unpack(cb.pack()).code == "en"

    def test_onboard_cb_roundtrip(self):
        from app.keyboards.callbacks import OnboardCb
        cb = OnboardCb(action="skip")
        assert OnboardCb.unpack(cb.pack()).action == "skip"


# =====================================================================
# KEYBOARDS
# =====================================================================


class TestMainMenuKeyboard:
    """Test main_menu_kb, cancel_kb, onboarding_skip_kb."""

    def test_main_menu_has_five_buttons(self):
        from app.keyboards.main_menu import main_menu_kb
        kb = main_menu_kb("ru")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 5  # feed, events, wishes, people, settings

    def test_main_menu_en(self):
        from app.keyboards.main_menu import main_menu_kb
        kb = main_menu_kb("en")
        all_text = " ".join(btn.text for row in kb.inline_keyboard for btn in row)
        assert any(word in all_text.lower() for word in ["feed", "events", "wishes", "people", "settings"])

    def test_cancel_kb_has_cancel_button(self):
        from app.keyboards.main_menu import cancel_kb
        kb = cancel_kb("ru")
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "cancel"

    def test_onboarding_skip_kb_emoji_only(self):
        from app.keyboards.main_menu import onboarding_skip_kb
        kb = onboarding_skip_kb("en")
        assert len(kb.inline_keyboard) == 1
        btn = kb.inline_keyboard[0][0]
        assert btn.text == "\u23ed"
        assert "onb:" in btn.callback_data

    def test_onboarding_event_kb_skip_button(self):
        from app.keyboards.main_menu import onboarding_event_kb
        kb = onboarding_event_kb("ru")
        assert len(kb.inline_keyboard) == 1
        buttons = kb.inline_keyboard[0]
        assert len(buttons) == 1
        assert "onb:" in buttons[0].callback_data


class TestEventsKeyboard:
    """Test event keyboard builders."""

    def test_events_list_empty(self):
        from app.keyboards.events import events_list_kb
        kb = events_list_kb([], 0, 0, "ru")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) >= 2
        assert any("ev:" in btn.callback_data for btn in buttons)

    def test_events_list_with_items(self):
        from app.keyboards.events import events_list_kb
        evs = [_make_event_obj(title=f"Event {i}") for i in range(3)]
        kb = events_list_kb(evs, 0, 3, "ru")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 5

    def test_events_list_pagination_appears(self):
        from app.keyboards.events import PAGE_SIZE, events_list_kb
        evs = [_make_event_obj() for _ in range(PAGE_SIZE)]
        kb = events_list_kb(evs, 0, PAGE_SIZE + 5, "ru")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("pg:" in cb for cb in all_cbs)

    def test_event_view_kb_has_edit_delete_dates(self):
        from app.keyboards.events import event_view_kb
        ev = _make_event_obj()
        kb = event_view_kb(ev, "en")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("edit" in cb for cb in all_cbs)
        assert any("delete" in cb for cb in all_cbs)
        assert any("dates" in cb for cb in all_cbs)

    def test_event_edit_kb_has_fields(self):
        from app.keyboards.events import event_edit_kb
        kb = event_edit_kb("test-id", "ru")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("title" in cb for cb in all_cbs)
        assert any("date" in cb for cb in all_cbs)
        assert any("description" in cb for cb in all_cbs)
        assert any("people" in cb for cb in all_cbs)

    def test_event_delete_confirm_kb(self):
        from app.keyboards.events import event_delete_confirm_kb
        kb = event_delete_confirm_kb("test-id", "ru")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 2

    def test_event_skip_kb_has_cancel(self):
        from app.keyboards.events import event_skip_kb
        kb = event_skip_kb("ru")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "skip" in all_cbs
        assert "cancel" in all_cbs


class TestWishesKeyboard:
    """Test wish keyboard builders."""

    def test_wishes_list_empty(self):
        from app.keyboards.wishes import wishes_list_kb
        kb = wishes_list_kb([], 0, 0, "en")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) >= 2  # create + back

    def test_wishes_list_text_preview_truncation(self):
        from app.keyboards.wishes import wishes_list_kb
        long_wish = _make_wish_obj(text="A" * 100)
        kb = wishes_list_kb([long_wish], 0, 1, "ru")
        first_btn = kb.inline_keyboard[0][0]
        assert "..." in first_btn.text

    def test_wish_view_kb(self):
        from app.keyboards.wishes import wish_view_kb
        n = _make_wish_obj()
        kb = wish_view_kb(n, "ru")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("edit" in cb for cb in all_cbs)
        assert any("delete" in cb for cb in all_cbs)

    def test_wish_skip_kb_has_cancel(self):
        from app.keyboards.wishes import wish_skip_kb
        kb = wish_skip_kb("en")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "skip" in all_cbs
        assert "cancel" in all_cbs


class TestPeopleKeyboard:
    """Test person keyboard builders."""

    def test_people_list_empty(self):
        from app.keyboards.people import people_list_kb
        kb = people_list_kb([], 0, 0, "ru")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) >= 2  # create + back

    def test_people_list_with_items(self):
        from app.keyboards.people import people_list_kb
        people_items = [_make_person_obj(name=f"Person{i}") for i in range(3)]
        kb = people_list_kb(people_items, 0, 3, "en")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 5  # 3 people + create + back

    def test_person_view_kb(self):
        from app.keyboards.people import person_view_kb
        tg = _make_person_obj()
        kb = person_view_kb(tg, "ru")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("rename" in cb for cb in all_cbs)
        assert any("delete" in cb for cb in all_cbs)

    def test_person_delete_confirm_kb(self):
        from app.keyboards.people import person_delete_confirm_kb
        kb = person_delete_confirm_kb("test-id", "en")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 2


class TestSettingsKeyboard:
    """Test settings keyboard builders."""

    def test_settings_kb_has_all_options(self, session: AsyncSession):
        from app.keyboards.settings import settings_kb
        user = MagicMock(spec=User)
        user.notifications_enabled = True
        user.spoiler_enabled = False
        user.timezone = "Europe/Moscow"
        kb = settings_kb(user, "ru")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 5

    def test_settings_kb_language_label_ru(self):
        from app.keyboards.settings import settings_kb
        user = MagicMock(spec=User)
        user.notifications_enabled = True
        user.spoiler_enabled = True
        user.timezone = "UTC"
        kb = settings_kb(user, "ru")
        first_text = kb.inline_keyboard[0][0].text
        assert "\U0001f1f7\U0001f1fa" in first_text  # RU flag

    def test_language_select_kb_no_back(self):
        from app.keyboards.settings import language_select_kb
        kb = language_select_kb()
        assert len(kb.inline_keyboard) == 1  # only language row, no back

    def test_language_select_kb_with_back(self):
        from app.keyboards.settings import language_select_kb
        kb = language_select_kb(back_lang="en")
        assert len(kb.inline_keyboard) == 2  # language row + back row
        back_btn = kb.inline_keyboard[1][0]
        assert "set:" in back_btn.callback_data


class TestFeedKeyboard:

    def test_feed_card_kb_first_page(self):
        from app.keyboards.feed import feed_card_kb
        bd = _make_bd_obj()
        kb = feed_card_kb(bd, 0, 5, "ru")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("share" in cb for cb in all_cbs)
        assert any("wishes" in cb for cb in all_cbs)
        assert not any("page=-1" in cb for cb in all_cbs if cb)

    def test_feed_card_kb_middle_page(self):
        from app.keyboards.feed import feed_card_kb
        bd = _make_bd_obj()
        kb = feed_card_kb(bd, 2, 5, "en")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any(cb and "card" in cb and cb.endswith(":1") for cb in all_cbs)
        assert any(cb and "card" in cb and cb.endswith(":3") for cb in all_cbs)

    def test_feed_card_kb_single_item(self):
        from app.keyboards.feed import feed_card_kb
        bd = _make_bd_obj()
        kb = feed_card_kb(bd, 0, 1, "ru")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert not any(cb and "card" in cb for cb in all_cbs)


class TestPagination:
    """Test pagination_row logic."""

    def test_first_page_no_prev(self):
        from app.keyboards.pagination import pagination_row
        row = pagination_row("events", 0, 20, 5, "ru")
        cbs = [btn.callback_data for btn in row]
        assert not any("page=0" in cb and "pg:" in cb for cb in cbs if cb != "noop")  # no prev on first page
        assert any("noop" in cb for cb in cbs)  # page counter

    def test_last_page_no_next(self):
        from app.keyboards.pagination import pagination_row
        row = pagination_row("events", 3, 20, 5, "ru")
        texts = [btn.text for btn in row]
        assert "4/4" in texts
        assert len(row) == 2  # prev + counter

    def test_middle_page_both_arrows(self):
        from app.keyboards.pagination import pagination_row
        row = pagination_row("wishes", 1, 15, 5, "ru")
        assert len(row) == 3  # prev + counter + next

    def test_single_page_no_arrows(self):
        from app.keyboards.pagination import pagination_row
        row = pagination_row("people", 0, 3, 5, "ru")
        assert len(row) == 1  # just counter

    def test_page_counter_text(self):
        from app.keyboards.pagination import pagination_row
        row = pagination_row("feed", 2, 30, 5, "ru")
        counter = next(btn for btn in row if btn.callback_data == "noop")
        assert counter.text == "3/6"


# =====================================================================
# FSM STATES
# =====================================================================


class TestFSMStates:
    """Verify all FSM state groups have expected states."""

    def test_onboarding_states(self):
        from app.handlers.states import OnboardingStates
        assert OnboardingStates.waiting_language
        assert OnboardingStates.waiting_first_event
        assert OnboardingStates.waiting_first_wish

    def test_event_create_states(self):
        from app.handlers.states import EventCreateStates
        assert EventCreateStates.waiting_title
        assert EventCreateStates.waiting_date
        assert EventCreateStates.waiting_description
        assert EventCreateStates.waiting_people

    def test_event_edit_states(self):
        from app.handlers.states import EventEditStates
        assert EventEditStates.waiting_title
        assert EventEditStates.waiting_date
        assert EventEditStates.waiting_description
        assert EventEditStates.waiting_people

    def test_wish_create_states(self):
        from app.handlers.states import WishCreateStates
        assert WishCreateStates.waiting_text
        assert WishCreateStates.waiting_reminder
        assert WishCreateStates.waiting_people

    def test_wish_edit_states(self):
        from app.handlers.states import WishEditStates
        assert WishEditStates.waiting_text
        assert WishEditStates.waiting_reminder
        assert WishEditStates.waiting_people

    def test_person_states(self):
        from app.handlers.states import PersonCreateStates, PersonRenameStates
        assert PersonCreateStates.waiting_name
        assert PersonRenameStates.waiting_name

    def test_settings_states(self):
        from app.handlers.states import SettingsStates
        assert SettingsStates.waiting_timezone
        assert SettingsStates.waiting_day_before_time
        assert SettingsStates.waiting_week_before_time
        assert SettingsStates.waiting_digest_time


# =====================================================================
# SCHEMAS
# =====================================================================


class TestSchemas:
    """Test Pydantic schema validation rules."""

    def test_user_create_requires_id(self):
        from pydantic import ValidationError

        from app.schemas.user import UserCreate
        try:
            UserCreate()  # type: ignore[call-arg]
            raise AssertionError("Should require id")
        except ValidationError:
            pass

    def test_user_create_defaults(self):
        from app.schemas.user import UserCreate
        u = UserCreate(id=123)
        assert u.language == "ru"
        assert u.timezone == "Europe/Moscow"
        assert u.notifications_enabled is True

    def test_event_create_requires_title_and_date(self):
        from pydantic import ValidationError

        from app.schemas.event import EventCreate
        try:
            EventCreate()  # type: ignore[call-arg]
            raise AssertionError("Should require title and event_date")
        except ValidationError:
            pass

    def test_event_create_person_names_default_empty(self):
        from app.schemas.event import EventCreate
        e = EventCreate(title="Test", event_date=date(2023, 1, 1))
        assert e.person_names == []

    def test_event_update_all_optional(self):
        from app.schemas.event import EventUpdate
        u = EventUpdate()
        assert u.title is None
        assert u.person_names is None

    def test_wish_create_requires_text(self):
        from pydantic import ValidationError

        from app.schemas.wish import WishCreate
        try:
            WishCreate()  # type: ignore[call-arg]
            raise AssertionError("Should require text")
        except ValidationError:
            pass

    def test_wish_create_person_names_default_empty(self):
        from app.schemas.wish import WishCreate
        w = WishCreate(text="Hello")
        assert w.person_names == []
        assert w.reminder_date is None

    def test_wish_update_all_optional(self):
        from app.schemas.wish import WishUpdate
        u = WishUpdate()
        assert u.text is None

    def test_user_update_all_optional(self):
        from app.schemas.user import UserUpdate
        u = UserUpdate()
        assert u.language is None
        assert u.onboarding_completed is None


# =====================================================================
# MIDDLEWARES
# =====================================================================


class TestDbSessionMiddleware:
    """Test DB session middleware injects session and handles commit/rollback."""

    async def test_injects_session_and_commits(self):
        from app.middlewares.db import DbSessionMiddleware

        mw = DbSessionMiddleware()
        mock_session = AsyncMock()
        mock_handler = AsyncMock(return_value="ok")
        event = MagicMock()
        data: dict = {}

        with patch("app.middlewares.db.async_session_factory") as factory:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_session)
            ctx.__aexit__ = AsyncMock(return_value=False)
            factory.return_value = ctx

            result = await mw(mock_handler, event, data)

        assert result == "ok"
        mock_session.commit.assert_awaited_once()

    async def test_rollback_on_exception(self):
        from app.middlewares.db import DbSessionMiddleware

        mw = DbSessionMiddleware()
        mock_session = AsyncMock()
        mock_handler = AsyncMock(side_effect=ValueError("boom"))
        event = MagicMock()
        data: dict = {}

        with patch("app.middlewares.db.async_session_factory") as factory:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_session)
            ctx.__aexit__ = AsyncMock(return_value=False)
            factory.return_value = ctx

            try:
                await mw(mock_handler, event, data)
                raise AssertionError("Should raise")
            except ValueError:
                pass

        mock_session.rollback.assert_awaited_once()


class TestUserMiddleware:
    """Test user upsert middleware."""

    async def test_injects_user_when_tg_user_present(self):
        from app.middlewares.user import UserMiddleware

        mw = UserMiddleware()
        mock_handler = AsyncMock(return_value="ok")
        event = MagicMock()

        tg_user = MagicMock()
        tg_user.id = 999
        tg_user.username = "testbot"
        tg_user.first_name = "Bot"

        mock_session = AsyncMock()
        mock_user = MagicMock()

        data: dict = {"event_from_user": tg_user, "session": mock_session}

        with patch("app.middlewares.user.get_or_create_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (mock_user, True)
            await mw(mock_handler, event, data)

        assert data["user"] is mock_user
        mock_handler.assert_awaited_once()

    async def test_skips_when_no_tg_user(self):
        from app.middlewares.user import UserMiddleware

        mw = UserMiddleware()
        mock_handler = AsyncMock(return_value="ok")
        event = MagicMock()
        data: dict = {}

        result = await mw(mock_handler, event, data)
        assert result == "ok"
        assert "user" not in data


class TestI18nMiddleware:
    """Test i18n middleware injects lang."""

    async def test_injects_lang_from_user(self):
        from app.middlewares.i18n import I18nMiddleware

        mw = I18nMiddleware()
        mock_handler = AsyncMock()
        event = MagicMock()
        mock_user = MagicMock()
        mock_user.language = "en"
        data: dict = {"user": mock_user}

        await mw(mock_handler, event, data)
        assert data["lang"] == "en"
        assert callable(data["t"])

    async def test_default_lang_when_no_user(self):
        from app.middlewares.i18n import I18nMiddleware

        mw = I18nMiddleware()
        mock_handler = AsyncMock()
        event = MagicMock()
        data: dict = {}

        await mw(mock_handler, event, data)
        assert data["lang"] == "ru"


class TestRateLimitMiddleware:
    """Test rate limit middleware."""

    async def test_allows_within_limit(self):
        from app.middlewares.rate_limit import RateLimitMiddleware

        mw = RateLimitMiddleware(max_per_minute=5)
        mock_handler = AsyncMock(return_value="ok")
        msg = MagicMock(spec=["from_user", "answer"])
        msg.from_user = MagicMock()
        msg.from_user.id = 42
        msg.answer = AsyncMock()
        data: dict = {}

        result = await mw(mock_handler, msg, data)
        assert result == "ok"
        mock_handler.assert_awaited_once()

    async def test_blocks_over_limit(self):
        from app.middlewares.rate_limit import RateLimitMiddleware

        mw = RateLimitMiddleware(max_per_minute=2)
        mock_handler = AsyncMock(return_value="ok")

        msg = MagicMock(spec=["from_user", "answer"])
        msg.from_user = MagicMock()
        msg.from_user.id = 42
        msg.answer = AsyncMock()
        msg.__class__ = type("Message", (), {})

        from aiogram.types import Message

        data: dict = {"lang": "ru"}

        real_msg = MagicMock(spec=Message)
        real_msg.from_user = MagicMock()
        real_msg.from_user.id = 42
        real_msg.answer = AsyncMock()

        for _ in range(2):
            await mw(mock_handler, real_msg, data)
        result = await mw(mock_handler, real_msg, data)

        assert result is None  # blocked
        real_msg.answer.assert_called()  # sent rate limit message

    async def test_passes_non_message_events(self):
        from app.middlewares.rate_limit import RateLimitMiddleware

        mw = RateLimitMiddleware(max_per_minute=1)
        mock_handler = AsyncMock(return_value="ok")
        cb = MagicMock()  # Not a Message
        data: dict = {}

        result = await mw(mock_handler, cb, data)
        assert result == "ok"


# =====================================================================
# ERROR HANDLER
# =====================================================================


class TestErrorHandler:
    """Test global error handler."""

    async def test_error_handler_returns_true(self):
        from app.handlers.errors import error_handler

        event = MagicMock()
        event.update.update_id = 123
        event.exception = ValueError("test error")
        event.update.message = MagicMock()
        event.update.message.answer = AsyncMock()
        event.update.callback_query = None

        result = await error_handler(event)
        assert result is True
        event.update.message.answer.assert_awaited_once()

    async def test_error_handler_callback_query(self):
        from app.handlers.errors import error_handler

        event = MagicMock()
        event.update.update_id = 456
        event.exception = RuntimeError("oops")
        event.update.message = None
        event.update.callback_query = MagicMock()
        event.update.callback_query.answer = AsyncMock()

        result = await error_handler(event)
        assert result is True
        event.update.callback_query.answer.assert_awaited_once()

    async def test_error_handler_survives_send_failure(self):
        from app.handlers.errors import error_handler

        event = MagicMock()
        event.update.update_id = 789
        event.exception = RuntimeError("oops")
        event.update.message = MagicMock()
        event.update.message.answer = AsyncMock(side_effect=Exception("send failed"))
        event.update.callback_query = None

        result = await error_handler(event)
        assert result is True  # still returns True, doesn't crash


# =====================================================================
# CONFIG
# =====================================================================


class TestConfig:
    """Test config property generation."""

    def test_database_url_format(self):
        from app.config import settings
        url = settings.database_url
        assert url.startswith("postgresql+asyncpg://")
        assert settings.db_name in url

    def test_database_url_sync_format(self):
        from app.config import settings
        url = settings.database_url_sync
        assert url.startswith("postgresql://")
        assert "asyncpg" not in url

    def test_redis_url_format(self):
        from app.config import settings
        url = settings.redis_url
        assert url.startswith("redis://")

    def test_app_debug_default(self):
        from app.config import settings
        assert isinstance(settings.app_debug, bool)


# =====================================================================
# CACHE SERVICE (mocked Redis)
# =====================================================================


class TestCacheService:
    """Test cache service with mocked Redis."""

    async def test_get_cached_feed_count_miss(self):
        from app.services.cache import get_cached_feed_count

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.services.cache._get_redis", return_value=mock_redis):
            result = await get_cached_feed_count(42)
        assert result is None

    async def test_get_cached_feed_count_hit(self):
        from app.services.cache import get_cached_feed_count

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="15")

        with patch("app.services.cache._get_redis", return_value=mock_redis):
            result = await get_cached_feed_count(42)
        assert result == 15

    async def test_set_cached_feed_count(self):
        from app.services.cache import set_cached_feed_count

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.services.cache._get_redis", return_value=mock_redis):
            await set_cached_feed_count(42, 10)
        mock_redis.set.assert_awaited_once()

    async def test_invalidate_user_feed_cache(self):
        from app.services.cache import invalidate_user_feed_cache

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        async def mock_scan_iter(pattern):
            for key in ["feed:42:0:10", "feed:42:10:10"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter

        with patch("app.services.cache._get_redis", return_value=mock_redis):
            await invalidate_user_feed_cache(42)

        assert mock_redis.delete.await_count >= 1

    async def test_cache_error_returns_none(self):
        from app.services.cache import get_cached_feed_count

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("connection refused"))

        with patch("app.services.cache._get_redis", return_value=mock_redis):
            result = await get_cached_feed_count(42)
        assert result is None  # graceful degradation


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test that all expected metrics are defined."""

    def test_message_counter_exists(self):
        from app.utils.metrics import messages_total
        assert messages_total is not None

    def test_ai_metrics_exist(self):
        from app.utils.metrics import ai_latency_seconds, ai_requests_total
        assert ai_requests_total is not None
        assert ai_latency_seconds is not None

    def test_entity_gauges_exist(self):
        from app.utils.metrics import events_total, wishes_total
        assert events_total is not None
        assert wishes_total is not None

    def test_notification_counter_exists(self):
        from app.utils.metrics import notifications_sent_total
        assert notifications_sent_total is not None

    def test_error_counter_exists(self):
        from app.utils.metrics import errors_total
        assert errors_total is not None

    def test_active_users_gauge_exists(self):
        from app.utils.metrics import active_users
        assert active_users is not None
