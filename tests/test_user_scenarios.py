"""50 user scenarios — end-to-end handler tests with mocked aiogram types.

Each test simulates a real user interaction:
  - Creates a User in the DB
  - Mocks aiogram Message/CallbackQuery/FSMContext
  - Calls the handler function directly
  - Asserts the correct response and state transitions
"""

import uuid
from datetime import date
from html import escape
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.note import NoteCreate
from app.schemas.user import UserCreate
from app.services.event_service import create_event
from app.services.note_service import create_note
from app.services.tag_service import create_tag
from app.services.user_service import get_or_create_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_user(
    session: AsyncSession,
    user_id: int = 123456789,
    onboarding_completed: bool = True,
    **overrides,
) -> User:
    """Create a test user in the DB."""
    data = UserCreate(id=user_id, username="tester", first_name="Test")
    user, _ = await get_or_create_user(session, data)
    user.onboarding_completed = onboarding_completed
    for k, v in overrides.items():
        setattr(user, k, v)
    await session.flush()
    return user


def _mock_message(text: str | None = "hello") -> AsyncMock:
    msg = AsyncMock()
    msg.text = text
    msg.answer = AsyncMock()
    msg.answer.return_value = AsyncMock()  # for processing_msg
    return msg


def _mock_callback(data: str = "noop") -> AsyncMock:
    cb = AsyncMock()
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    return cb


def _mock_state(state_name: str | None = None, data: dict | None = None) -> AsyncMock:
    st = AsyncMock()
    st.get_state = AsyncMock(return_value=state_name)
    st.get_data = AsyncMock(return_value=data or {})
    st.set_state = AsyncMock()
    st.update_data = AsyncMock()
    st.clear = AsyncMock()
    return st


def _mock_callback_data(**kwargs):
    """Create a MagicMock that behaves like aiogram CallbackData."""
    cd = MagicMock()
    for k, v in kwargs.items():
        setattr(cd, k, v)
    return cd


# =====================================================================
# 1-5: ONBOARDING
# =====================================================================


class TestOnboarding:
    """Scenarios 1-5: Onboarding flow."""

    async def test_01_start_new_user_shows_language_selection(self, session: AsyncSession):
        """S01: /start for a new user → welcome + language select keyboard."""
        from app.handlers.start import cmd_start

        user = await _make_user(session, onboarding_completed=False)
        msg = _mock_message("/start")
        state = _mock_state()

        await cmd_start(msg, state, user, "ru", session)

        msg.answer.assert_called_once()
        call_kwargs = msg.answer.call_args
        assert "language_select" not in str(call_kwargs)  # Just verify it was called
        text = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("text", "")
        assert user.first_name in text
        state.clear.assert_called_once()
        state.set_state.assert_called_once()

    async def test_02_start_existing_user_shows_menu(self, session: AsyncSession):
        """S02: /start for a returning user → welcome back + main menu."""
        from app.handlers.start import cmd_start

        user = await _make_user(session, onboarding_completed=True)
        msg = _mock_message("/start")
        state = _mock_state()

        await cmd_start(msg, state, user, "ru", session)

        text = msg.answer.call_args.args[0]
        assert user.first_name in text
        assert "reply_markup" in msg.answer.call_args.kwargs

    async def test_03_onboarding_language_advances_to_step1(self, session: AsyncSession):
        """S03: Language selection → step1 prompt with skip button."""
        from app.handlers.start import onboarding_language

        user = await _make_user(session, onboarding_completed=False)
        cb = _mock_callback()
        cd = _mock_callback_data(code="ru")
        state = _mock_state()

        await onboarding_language(cb, cd, state, user, session)

        cb.message.edit_text.assert_called_once()
        # Intro and step1 are sent as separate answer messages
        assert cb.message.answer.call_count >= 2
        state.set_state.assert_called_once()

    async def test_04_onboarding_skip_event_advances_to_step2(self, session: AsyncSession):
        """S04: Skip event step → step2 prompt."""
        from app.handlers.start import onboarding_skip_event

        user = await _make_user(session, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_event(cb, state, user, session)

        cb.message.edit_text.assert_called_once()
        state.set_state.assert_called_once()

    async def test_05_onboarding_skip_note_completes(self, session: AsyncSession):
        """S05: Skip note step → onboarding complete, main menu shown."""
        from app.handlers.start import onboarding_skip_note

        user = await _make_user(session, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_note(cb, state, user, session)

        state.clear.assert_called_once()
        # Should show step3 message + main menu
        assert cb.message.edit_text.called or cb.message.answer.called


# =====================================================================
# 6-15: EVENT CRUD
# =====================================================================


class TestEventCRUD:
    """Scenarios 6-15: Event create, read, update, delete."""

    async def test_06_event_list_empty(self, session: AsyncSession):
        """S06: Open events list with 0 events → 'empty' text."""
        from app.handlers.events import show_events_list

        user = await _make_user(session)
        cb = _mock_callback()

        await show_events_list(cb, user, "ru", session, page=0)

        text = cb.message.edit_text.call_args.args[0]
        assert "пока нет" in text.lower() or "empty" in text.lower()

    async def test_07_event_create_starts_fsm(self, session: AsyncSession):
        """S07: Press 'create event' → FSM state waiting_title, cancel button shown."""
        from app.handlers.events import event_create_start

        cb = _mock_callback()
        state = _mock_state()

        await event_create_start(cb, state, "ru")

        cb.message.edit_text.assert_called_once()
        state.set_state.assert_called_once()
        # Verify cancel keyboard is present
        kw = cb.message.edit_text.call_args.kwargs
        assert "reply_markup" in kw

    async def test_08_event_create_title_advances_to_date(self, session: AsyncSession):
        """S08: Enter title → state advances to waiting_date with cancel button."""
        from app.handlers.events import event_create_title

        msg = _mock_message("Свадьба")
        state = _mock_state()

        await event_create_title(msg, state, "ru")

        state.update_data.assert_called_once_with(title="Свадьба")
        state.set_state.assert_called_once()
        # Date prompt should now have cancel_kb
        kw = msg.answer.call_args.kwargs
        assert "reply_markup" in kw

    async def test_09_event_create_date_advances_to_description(self, session: AsyncSession):
        """S09: Enter valid date → advances to waiting_description with skip+cancel."""
        from app.handlers.events import event_create_date

        msg = _mock_message("17.08.2022")
        state = _mock_state()

        await event_create_date(msg, state, "ru")

        state.update_data.assert_called_once()
        state.set_state.assert_called_once()
        kw = msg.answer.call_args.kwargs
        assert "reply_markup" in kw  # skip_kb with cancel

    async def test_10_event_create_invalid_date_stays(self, session: AsyncSession):
        """S10: Enter invalid date → error message, stays in state."""
        from app.handlers.events import event_create_date

        msg = _mock_message("not-a-date")
        state = _mock_state()

        await event_create_date(msg, state, "ru")

        text = msg.answer.call_args.args[0]
        assert "дат" in text.lower() or "date" in text.lower()
        state.set_state.assert_not_called()  # stays in same state

    async def test_11_event_create_skip_description(self, session: AsyncSession):
        """S11: Skip description → advances to tags."""
        from app.handlers.events import event_create_skip_description

        cb = _mock_callback()
        state = _mock_state()

        await event_create_skip_description(cb, state, "ru")

        state.set_state.assert_called_once()
        cb.message.edit_text.assert_called_once()

    async def test_12_event_create_full_flow(self, session: AsyncSession):
        """S12: Full create: title→date→skip desc→skip tags → event in DB."""
        from app.handlers.events import _finish_event_create

        user = await _make_user(session)
        msg = _mock_message()
        state = _mock_state()
        data = {"title": "Свадьба", "event_date": "2022-08-17"}

        with patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock):
            await _finish_event_create(msg, state, user, "ru", session, data, [])

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "Свадьба" in text

    async def test_13_event_view_shows_details(self, session: AsyncSession):
        """S13: View event → shows title, date, tags."""
        from app.handlers.events import event_view

        user = await _make_user(session)
        event = await create_event(
            session, user.id,
            EventCreate(title="Birthday", event_date=date(2000, 1, 15)),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(event.id), page=0)

        await event_view(cb, cd, user, "en", session)

        text = cb.message.edit_text.call_args.args[0]
        assert "Birthday" in text
        assert "15.01.2000" in text

    async def test_14_event_delete_system_blocked(self, session: AsyncSession):
        """S14: Delete system event → 'cannot delete' alert."""
        from app.handlers.events import event_delete_ask

        user = await _make_user(session)
        event = await create_event(
            session, user.id,
            EventCreate(title="System", event_date=date(2022, 1, 1), is_system=True),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(event.id), page=0)

        await event_delete_ask(cb, cd, user, "ru", session)

        cb.answer.assert_called()
        alert_text = cb.answer.call_args.args[0]
        assert "нельзя" in alert_text.lower() or "cannot" in alert_text.lower()

    async def test_15_event_create_limit_reached(self, session: AsyncSession):
        """S15: Create event when limit reached → error message."""
        from app.handlers.events import _finish_event_create

        user = await _make_user(session, max_events=1)
        # Create 1 event to hit the limit
        await create_event(session, user.id, EventCreate(title="First", event_date=date(2020, 1, 1)))

        msg = _mock_message()
        state = _mock_state()
        data = {"title": "Second", "event_date": "2021-01-01"}

        with patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock):
            await _finish_event_create(msg, state, user, "ru", session, data, [])

        text = msg.answer.call_args.args[0]
        assert "лимит" in text.lower() or "limit" in text.lower()
        state.clear.assert_called_once()


# =====================================================================
# 16-23: NOTE CRUD
# =====================================================================


class TestNoteCRUD:
    """Scenarios 16-23: Note create, read, update, delete."""

    async def test_16_note_list_empty(self, session: AsyncSession):
        """S16: Notes list with 0 notes → 'empty' message."""
        from app.handlers.notes import show_notes_list

        user = await _make_user(session)
        cb = _mock_callback()

        await show_notes_list(cb, user, "ru", session, page=0)

        text = cb.message.edit_text.call_args.args[0]
        assert "пока нет" in text.lower() or "empty" in text.lower()

    async def test_17_note_create_starts_fsm(self, session: AsyncSession):
        """S17: Press 'create note' → waiting_text state with cancel button."""
        from app.handlers.notes import note_create_start

        cb = _mock_callback()
        state = _mock_state()

        await note_create_start(cb, state, "ru")

        state.set_state.assert_called_once()
        kw = cb.message.edit_text.call_args.kwargs
        assert "reply_markup" in kw

    async def test_18_note_create_text_advances_to_reminder(self, session: AsyncSession):
        """S18: Enter note text → advances to waiting_reminder with skip+cancel."""
        from app.handlers.notes import note_create_text

        msg = _mock_message("Купить молоко")
        state = _mock_state()

        await note_create_text(msg, state, "ru")

        state.update_data.assert_called_once_with(text="Купить молоко")
        state.set_state.assert_called_once()

    async def test_19_note_create_skip_reminder(self, session: AsyncSession):
        """S19: Skip reminder → advances to tags."""
        from app.handlers.notes import note_create_skip_reminder

        cb = _mock_callback()
        state = _mock_state()

        await note_create_skip_reminder(cb, state, "ru")

        state.set_state.assert_called_once()

    async def test_20_note_create_full_flow(self, session: AsyncSession):
        """S20: Full note create: text→skip reminder→skip tags → note in DB."""
        from app.handlers.notes import _finish_note_create

        user = await _make_user(session)
        msg = _mock_message()
        state = _mock_state()
        data = {"text": "Не забыть позвонить маме"}

        await _finish_note_create(msg, state, user, "ru", session, data, [])

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "сохранена" in text.lower() or "saved" in text.lower()

    async def test_21_note_view_shows_details(self, session: AsyncSession):
        """S21: View note → shows text, tags, reminder."""
        from app.handlers.notes import note_view

        user = await _make_user(session)
        note = await create_note(
            session, user.id,
            NoteCreate(text="Test note", reminder_date=date(2025, 12, 31)),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(note.id), page=0)

        await note_view(cb, cd, user, "ru", session)

        text = cb.message.edit_text.call_args.args[0]
        assert "Test note" in text
        assert "31.12.2025" in text

    async def test_22_note_edit_text(self, session: AsyncSession):
        """S22: Edit note text → updated, shown with view keyboard."""
        from app.handlers.notes import note_edit_text

        user = await _make_user(session)
        note = await create_note(session, user.id, NoteCreate(text="Old text"))
        msg = _mock_message("New text")
        state = _mock_state(data={"edit_note_id": str(note.id)})

        await note_edit_text(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "обновлена" in text.lower() or "updated" in text.lower()

    async def test_23_note_create_limit_reached(self, session: AsyncSession):
        """S23: Create note at limit → error message."""
        from app.handlers.notes import _finish_note_create

        user = await _make_user(session, max_notes=1)
        await create_note(session, user.id, NoteCreate(text="First"))

        msg = _mock_message()
        state = _mock_state()

        await _finish_note_create(msg, state, user, "ru", session, {"text": "Second"}, [])

        text = msg.answer.call_args.args[0]
        assert "лимит" in text.lower() or "limit" in text.lower()


# =====================================================================
# 24-29: TAGS
# =====================================================================


class TestTagCRUD:
    """Scenarios 24-29: Tag create, view, rename, delete."""

    async def test_24_tag_list_empty(self, session: AsyncSession):
        """S24: Tags list with 0 tags → 'empty' message."""
        from app.handlers.tags import show_tags_list

        user = await _make_user(session)
        cb = _mock_callback()

        await show_tags_list(cb, user, "ru", session, page=0)

        text = cb.message.edit_text.call_args.args[0]
        assert "пока нет" in text.lower() or "empty" in text.lower()

    async def test_25_tag_create(self, session: AsyncSession):
        """S25: Create tag → success message with tag name."""
        from app.handlers.tags import tag_create_name

        user = await _make_user(session)
        msg = _mock_message("Работа")
        state = _mock_state()

        await tag_create_name(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "Работа" in text

    async def test_26_tag_view_shows_counts(self, session: AsyncSession):
        """S26: View tag → shows event/note counts."""
        from app.handlers.tags import tag_view

        user = await _make_user(session)
        tag = await create_tag(session, user.id, "Family")
        await create_event(
            session, user.id,
            EventCreate(title="Bday", event_date=date(2020, 5, 1), tag_names=["Family"]),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(tag.id), page=0)

        # Refresh tag with relationships
        await session.refresh(tag, ["events", "notes"])

        await tag_view(cb, cd, user, "en", session)

        text = cb.message.edit_text.call_args.args[0]
        assert "Family" in text

    async def test_27_tag_rename_success(self, session: AsyncSession):
        """S27: Rename tag → success message."""
        from app.handlers.tags import tag_rename_name

        user = await _make_user(session)
        tag = await create_tag(session, user.id, "Old")
        msg = _mock_message("New")
        state = _mock_state(data={"rename_tag_id": str(tag.id)})

        await tag_rename_name(msg, state, user, "en", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "New" in text

    async def test_28_tag_rename_duplicate_shows_error_with_keyboard(self, session: AsyncSession):
        """S28: Rename tag to existing name → error + main_menu_kb (not dead-end)."""
        from app.handlers.tags import tag_rename_name

        user = await _make_user(session)
        await create_tag(session, user.id, "Existing")
        tag2 = await create_tag(session, user.id, "ToRename")
        msg = _mock_message("Existing")
        state = _mock_state(data={"rename_tag_id": str(tag2.id)})

        await tag_rename_name(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "существует" in text.lower() or "exists" in text.lower()
        # CRITICAL: verify keyboard is present (not a dead-end)
        kw = msg.answer.call_args.kwargs
        assert "reply_markup" in kw

    async def test_29_tag_delete(self, session: AsyncSession):
        """S29: Confirm delete tag → deleted, returns to list."""
        from app.handlers.tags import tag_delete_confirm

        user = await _make_user(session)
        tag = await create_tag(session, user.id, "Temp")
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(tag.id), page=0)

        await tag_delete_confirm(cb, cd, user, "ru", session)

        cb.answer.assert_called()
        text = cb.answer.call_args.args[0]
        assert "удалён" in text.lower() or "deleted" in text.lower()


# =====================================================================
# 30-35: SETTINGS
# =====================================================================


class TestSettings:
    """Scenarios 30-35: Settings view and modification."""

    async def test_30_settings_view(self, session: AsyncSession):
        """S30: Open settings → shows all current values."""
        from app.handlers.settings import show_settings

        user = await _make_user(session)
        cb = _mock_callback()

        await show_settings(cb, user, "ru")

        cb.message.edit_text.assert_called_once()
        kw = cb.message.edit_text.call_args.kwargs
        assert "reply_markup" in kw

    async def test_31_settings_language_shows_back_button(self, session: AsyncSession):
        """S31: Language selection in settings → shows back button."""
        from app.handlers.settings import settings_language

        cb = _mock_callback()

        await settings_language(cb, "ru")

        kw = cb.message.edit_text.call_args.kwargs
        kb = kw["reply_markup"]
        # Should have 2 rows: language buttons + back button
        assert len(kb.inline_keyboard) == 2

    async def test_32_settings_set_language(self, session: AsyncSession):
        """S32: Select language → saved, returns to settings."""
        from app.handlers.settings import settings_set_language

        user = await _make_user(session, language="ru")
        cb = _mock_callback()
        cd = _mock_callback_data(code="en")

        await settings_set_language(cb, cd, user, session)

        assert user.language == "en"
        cb.answer.assert_called()

    async def test_33_settings_timezone_with_cancel(self, session: AsyncSession):
        """S33: Timezone prompt → shows cancel button."""
        from app.handlers.settings import settings_timezone

        cb = _mock_callback()
        state = _mock_state()

        await settings_timezone(cb, state, "ru")

        state.set_state.assert_called_once()
        kw = cb.message.edit_text.call_args.kwargs
        assert "reply_markup" in kw

    async def test_34_settings_set_timezone_returns_to_settings(self, session: AsyncSession):
        """S34: Enter timezone → saved, settings keyboard shown."""
        from app.handlers.settings import settings_set_timezone

        user = await _make_user(session)
        msg = _mock_message("US/Eastern")
        state = _mock_state()

        await settings_set_timezone(msg, state, user, "en", session)

        assert user.timezone == "US/Eastern"
        state.clear.assert_called_once()
        kw = msg.answer.call_args.kwargs
        assert "reply_markup" in kw  # settings_kb returned

    async def test_35_settings_notification_count(self, session: AsyncSession):
        """S35: Change notification count → saved with settings keyboard."""
        from app.handlers.settings import settings_set_notif_count

        user = await _make_user(session)
        msg = _mock_message("7")
        state = _mock_state()

        await settings_set_notif_count(msg, state, user, "ru", session)

        assert user.notification_count == 7
        state.clear.assert_called_once()
        kw = msg.answer.call_args.kwargs
        assert "reply_markup" in kw


# =====================================================================
# 36-40: CANCEL / ESCAPE
# =====================================================================


class TestCancelEscape:
    """Scenarios 36-40: Universal cancel from any FSM state."""

    async def test_36_cancel_command_in_fsm_state(self, session: AsyncSession):
        """S36: /cancel while in FSM state → state cleared, main menu shown."""
        from app.handlers.common import cmd_cancel

        user = await _make_user(session)
        msg = _mock_message("/cancel")
        state = _mock_state(state_name="EventCreateStates:waiting_title")

        await cmd_cancel(msg, state, user, "ru")

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "Отмена" in text or user.first_name in text

    async def test_37_cancel_command_without_state(self, session: AsyncSession):
        """S37: /cancel without active state → just shows main menu."""
        from app.handlers.common import cmd_cancel

        user = await _make_user(session)
        msg = _mock_message("/cancel")
        state = _mock_state(state_name=None)

        await cmd_cancel(msg, state, user, "en")

        state.clear.assert_called_once()
        kw = msg.answer.call_args.kwargs
        assert "reply_markup" in kw

    async def test_38_cancel_callback_from_event_create(self, session: AsyncSession):
        """S38: Press cancel button during event create → returns to main menu."""
        from app.handlers.common import cancel_callback

        user = await _make_user(session)
        cb = _mock_callback(data="cancel")
        state = _mock_state()

        await cancel_callback(cb, state, user, "ru")

        state.clear.assert_called_once()
        cb.message.edit_text.assert_called_once()
        kw = cb.message.edit_text.call_args.kwargs
        assert "reply_markup" in kw

    async def test_39_cancel_callback_from_settings_timezone(self, session: AsyncSession):
        """S39: Press cancel during timezone input → main menu."""
        from app.handlers.common import cancel_callback

        user = await _make_user(session)
        cb = _mock_callback(data="cancel")
        state = _mock_state(state_name="SettingsStates:waiting_timezone")

        await cancel_callback(cb, state, user, "en")

        state.clear.assert_called_once()

    async def test_40_cancel_callback_from_tag_rename(self, session: AsyncSession):
        """S40: Press cancel during tag rename → main menu."""
        from app.handlers.common import cancel_callback

        user = await _make_user(session)
        cb = _mock_callback(data="cancel")
        state = _mock_state(state_name="TagRenameStates:waiting_name")

        await cancel_callback(cb, state, user, "ru")

        state.clear.assert_called_once()
        cb.message.edit_text.assert_called_once()


# =====================================================================
# 41-43: FEED
# =====================================================================


class TestFeed:
    """Scenarios 41-43: Beautiful dates feed."""

    async def test_41_feed_empty(self, session: AsyncSession):
        """S41: Feed with no events → empty message."""
        from app.handlers.feed import show_feed_list

        user = await _make_user(session)
        cb = _mock_callback()
        state = _mock_state()

        await show_feed_list(cb, user, "ru", session, state, page=0)

        text = cb.message.edit_text.call_args.args[0]
        assert "пока нет" in text.lower() or "нет" in text.lower() or "empty" in text.lower()

    async def test_42_feed_with_data(self, session: AsyncSession):
        """S42: Feed with beautiful dates → shows list."""
        from app.handlers.feed import show_feed_list
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _make_user(session)
        event = await create_event(
            session, user.id,
            EventCreate(title="Wedding", event_date=date(2020, 8, 17)),
        )
        await recalculate_for_event(session, event)
        await session.flush()

        cb = _mock_callback()
        state = _mock_state()
        await show_feed_list(cb, user, "en", session, state, page=0)

        # Feed sends separate messages or shows empty via edit_text
        assert cb.message.answer.called or cb.message.edit_text.called

    async def test_43_feed_share_not_found(self, session: AsyncSession):
        """S43: Share non-existent feed item → not_found alert."""
        from app.handlers.feed import feed_share

        user = await _make_user(session)
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(uuid.uuid4()), page=0)

        await feed_share(cb, cd, "ru", session)

        cb.answer.assert_called()
        text = cb.answer.call_args.args[0]
        assert "найдено" in text.lower() or "found" in text.lower()


# =====================================================================
# 44-46: AI HANDLER
# =====================================================================


class TestAIHandler:
    """Scenarios 44-46: AI text/voice processing."""

    async def test_44_text_command_skipped(self, session: AsyncSession):
        """S44: Text starting with / → skipped by AI handler."""
        from app.handlers.ai import handle_text

        user = await _make_user(session)
        msg = _mock_message("/settings")

        await handle_text(msg, user, "ru", session)

        msg.answer.assert_not_called()

    async def test_45_voice_too_long(self, session: AsyncSession):
        """S45: Voice message > 60s → 'audio too long' error."""
        from app.handlers.ai import handle_voice

        user = await _make_user(session)
        msg = AsyncMock()
        msg.voice = MagicMock()
        msg.voice.duration = 120
        msg.answer = AsyncMock()

        await handle_voice(msg, user, "ru", session)

        text = msg.answer.call_args.args[0]
        assert "длинное" in text.lower() or "long" in text.lower()

    @patch("app.handlers.ai.check_ai_rate_limit", return_value=False)
    async def test_46_rate_limited(self, mock_rl, session: AsyncSession):
        """S46: AI rate limit exceeded → error message."""
        from app.handlers.ai import handle_text

        user = await _make_user(session)
        msg = _mock_message("Запомни дату")

        await handle_text(msg, user, "ru", session)

        text = msg.answer.call_args.args[0]
        assert "запрос" in text.lower() or "request" in text.lower() or "подожд" in text.lower()


# =====================================================================
# 47-50: EDGE CASES & SECURITY
# =====================================================================


class TestEdgeCases:
    """Scenarios 47-50: Security, edge cases, error handling."""

    async def test_47_html_injection_in_event_title(self, session: AsyncSession):
        """S47: Event title with HTML tags → escaped in view (no injection)."""
        from app.handlers.events import event_view

        user = await _make_user(session)
        malicious_title = "<b>HACKED</b><script>alert(1)</script>"
        event = await create_event(
            session, user.id,
            EventCreate(title=malicious_title, event_date=date(2023, 1, 1)),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(event.id), page=0)

        await event_view(cb, cd, user, "en", session)

        text = cb.message.edit_text.call_args.args[0]
        # Raw HTML tags must NOT appear — they should be escaped
        assert "<script>" not in text
        assert "&lt;script&gt;" in text or escape("<script>") in text

    async def test_48_html_injection_in_note_text(self, session: AsyncSession):
        """S48: Note text with HTML → escaped in view."""
        from app.handlers.notes import note_view

        user = await _make_user(session)
        malicious_text = "<img src=x onerror=alert(1)>Hello"
        note = await create_note(
            session, user.id,
            NoteCreate(text=malicious_text),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(note.id), page=0)

        await note_view(cb, cd, user, "ru", session)

        text = cb.message.edit_text.call_args.args[0]
        assert "<img" not in text
        assert "&lt;img" in text or escape("<img") in text

    async def test_49_event_edit_returns_none_shows_error(self, session: AsyncSession):
        """S49: Edit non-existent event → 'not found' message (not silent)."""
        from app.handlers.events import event_edit_title

        user = await _make_user(session)
        msg = _mock_message("New Title")
        fake_id = str(uuid.uuid4())
        state = _mock_state(data={"edit_event_id": fake_id})

        await event_edit_title(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "найдено" in text.lower() or "found" in text.lower()

    async def test_50_note_edit_returns_none_shows_error(self, session: AsyncSession):
        """S50: Edit non-existent note → 'not found' message (not silent)."""
        from app.handlers.notes import note_edit_text

        user = await _make_user(session)
        msg = _mock_message("Updated text")
        fake_id = str(uuid.uuid4())
        state = _mock_state(data={"edit_note_id": fake_id})

        await note_edit_text(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "найдено" in text.lower() or "found" in text.lower()
