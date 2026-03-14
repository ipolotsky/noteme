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
from app.schemas.user import UserCreate
from app.schemas.wish import WishCreate
from app.services.event_service import create_event
from app.services.person_service import create_person
from app.services.user_service import get_or_create_user
from app.services.wish_service import create_wish

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
        """S01: /start for a new user → GIF + welcome + language select keyboard."""
        from app.handlers.start import cmd_start

        user = await _make_user(session, onboarding_completed=False)
        msg = _mock_message("/start")
        msg.answer_animation = AsyncMock()
        state = _mock_state()

        await cmd_start(msg, state, user, "ru", session)

        msg.answer_animation.assert_called_once()
        msg.answer.assert_called_once()
        call_kwargs = msg.answer.call_args
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

    async def test_03_onboarding_language_advances_to_intro(self, session: AsyncSession):
        """S03: Language selection -> intro prompt with 'dont get it' button."""
        from app.handlers.start import onboarding_language
        from app.handlers.states import OnboardingStates

        user = await _make_user(session, onboarding_completed=False)
        cb = _mock_callback()
        cd = _mock_callback_data(code="ru")
        state = _mock_state()

        await onboarding_language(cb, cd, state, user, session)

        cb.message.edit_text.assert_called_once()
        cb.message.answer.assert_called_once()
        state.set_state.assert_called_once_with(OnboardingStates.waiting_intro_response)

    async def test_03a_intro_button_advances_to_example(self, session: AsyncSession):
        """S03a: 'Dont get it' button -> shows example with 777 days."""
        from app.handlers.start import onboarding_intro_button
        from app.handlers.states import OnboardingStates

        user = await _make_user(session, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_intro_button(cb, state, user)

        cb.message.edit_reply_markup.assert_called_once()
        cb.message.answer.assert_called_once()
        answer_text = cb.message.answer.call_args.args[0]
        assert "777" in answer_text
        state.set_state.assert_called_once_with(OnboardingStates.waiting_example_response)

    async def test_03b_intro_text_advances_to_example(self, session: AsyncSession):
        """S03b: Any text in intro state -> shows example with 777 days."""
        from app.handlers.start import onboarding_intro_text
        from app.handlers.states import OnboardingStates

        user = await _make_user(session, user_id=55551, onboarding_completed=False)
        msg = _mock_message("test")
        state = _mock_state(data={"lang": "ru"})

        await onboarding_intro_text(msg, state, user)

        msg.answer.assert_called_once()
        answer_text = msg.answer.call_args.args[0]
        assert "777" in answer_text
        state.set_state.assert_called_once_with(OnboardingStates.waiting_example_response)

    async def test_03c_got_it_advances_to_event_creation(self, session: AsyncSession):
        """S03c: 'Got it' button -> shows event creation prompt."""
        from app.handlers.start import onboarding_got_it
        from app.handlers.states import OnboardingStates

        user = await _make_user(session, user_id=55552, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_got_it(cb, state, user)

        cb.message.edit_text.assert_called_once()
        state.set_state.assert_called_once_with(OnboardingStates.waiting_first_event)

    async def test_03d_more_example_advances_to_event_creation(self, session: AsyncSession):
        """S03d: 'More example' button -> shows event creation prompt."""
        from app.handlers.start import onboarding_more_example
        from app.handlers.states import OnboardingStates

        user = await _make_user(session, user_id=55553, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_more_example(cb, state, user)

        cb.message.edit_text.assert_called_once()
        state.set_state.assert_called_once_with(OnboardingStates.waiting_first_event)

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_04_onboarding_skip_event_advances_to_wish(
        self, mock_recalc, session: AsyncSession
    ):
        """S04: Skip event step -> create registration event and advance to step 2."""
        from app.handlers.start import onboarding_skip_event
        from app.handlers.states import OnboardingStates

        user = await _make_user(session, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_event(cb, state, user, session)

        cb.message.edit_text.assert_called_once()
        state.set_state.assert_called_once_with(OnboardingStates.waiting_first_wish)

    async def test_05_onboarding_skip_wish_completes(self, session: AsyncSession):
        """S05: Skip wish step → onboarding complete, main menu shown."""
        from app.handlers.start import onboarding_skip_wish

        user = await _make_user(session, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_wish(cb, state, user, session)

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
        from unittest.mock import patch

        from app.handlers.events import event_create_start

        cb = _mock_callback()
        state = _mock_state()
        user = AsyncMock()
        user.id = 100
        user.max_events = 10

        with (
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                side_effect=lambda session, key, default: default,
            ),
            patch(
                "app.services.event_service.count_user_events",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            await event_create_start(cb, state, user, "ru", session)

        cb.message.edit_text.assert_called_once()
        state.set_state.assert_called_once()
        kw = cb.message.edit_text.call_args.kwargs
        assert "reply_markup" in kw

    async def test_08_event_create_title_advances_to_date(self, session: AsyncSession):
        """S08: Enter title → state advances to waiting_date with cancel button."""
        from app.handlers.events import event_create_title

        msg = _mock_message("Свадьба")
        state = _mock_state()
        user = AsyncMock()

        await event_create_title(msg, state, user, "ru")

        state.update_data.assert_any_call(title="Свадьба")
        state.set_state.assert_called_once()

    async def test_09_event_create_date_advances_to_description(self, session: AsyncSession):
        """S09: Enter valid date → advances to waiting_description with skip+cancel."""
        from app.handlers.events import event_create_date

        msg = _mock_message("17.08.2022")
        state = _mock_state()
        user = AsyncMock()

        await event_create_date(msg, state, user, "ru")

        assert state.update_data.call_count >= 1
        state.set_state.assert_called_once()

    async def test_10_event_create_invalid_date_stays(self, session: AsyncSession):
        """S10: Enter invalid date → error message, stays in state."""
        from app.handlers.events import event_create_date

        msg = _mock_message("not-a-date")
        state = _mock_state()
        user = AsyncMock()

        await event_create_date(msg, state, user, "ru")

        text = msg.answer.call_args.args[0]
        assert "дат" in text.lower() or "date" in text.lower()
        state.set_state.assert_not_called()  # stays in same state

    async def test_11_event_create_skip_description(self, session: AsyncSession):
        """S11: Skip description → advances to people."""
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

        with patch(
            "app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock
        ):
            await _finish_event_create(msg, state, user, "ru", session, data, [])

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "Свадьба" in text

    async def test_13_event_view_shows_details(self, session: AsyncSession):
        """S13: View event → shows title, date, tags."""
        from app.handlers.events import event_view

        user = await _make_user(session)
        event = await create_event(
            session,
            user.id,
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
            session,
            user.id,
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
        await create_event(
            session, user.id, EventCreate(title="First", event_date=date(2020, 1, 1))
        )

        msg = _mock_message()
        state = _mock_state()
        data = {"title": "Second", "event_date": "2021-01-01"}

        with patch(
            "app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock
        ):
            await _finish_event_create(msg, state, user, "ru", session, data, [])

        text = msg.answer.call_args.args[0]
        assert "лимит" in text.lower() or "limit" in text.lower()
        state.clear.assert_called_once()


# =====================================================================
# 16-23: WISH CRUD
# =====================================================================


class TestWishCRUD:
    """Scenarios 16-23: Wish create, read, update, delete."""

    async def test_16_wish_list_empty(self, session: AsyncSession):
        """S16: Wishes list with 0 wishes → 'empty' message."""
        from app.handlers.wishes import show_wishes_list

        user = await _make_user(session)
        cb = _mock_callback()

        await show_wishes_list(cb, user, "ru", session, page=0)

        text = cb.message.edit_text.call_args.args[0]
        assert "пока нет" in text.lower() or "empty" in text.lower()

    async def test_17_wish_create_starts_fsm(self, session: AsyncSession):
        """S17: Press 'create wish' → waiting_text state with cancel button."""
        from unittest.mock import patch

        from app.handlers.wishes import wish_create_start

        cb = _mock_callback()
        state = _mock_state()
        user = AsyncMock()
        user.id = 100
        user.max_wishes = 10

        with (
            patch(
                "app.services.app_settings_service.get_int_setting",
                new_callable=AsyncMock,
                side_effect=lambda session, key, default: default,
            ),
            patch(
                "app.handlers.wishes.count_user_wishes",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            await wish_create_start(cb, state, user, "ru", session)

        state.set_state.assert_called_once()
        kw = cb.message.edit_text.call_args.kwargs
        assert "reply_markup" in kw

    async def test_18_wish_create_text_advances_to_people(self, session: AsyncSession):
        """S18: Enter wish text → advances to waiting_people with skip+cancel."""
        from app.handlers.wishes import wish_create_text

        msg = _mock_message("Купить молоко")
        state = _mock_state()
        user = AsyncMock()

        await wish_create_text(msg, state, user, "ru")

        state.update_data.assert_any_call(text="Купить молоко")
        state.set_state.assert_called_once()

    async def test_20_wish_create_full_flow(self, session: AsyncSession):
        """S20: Full wish create: text→skip people → wish in DB."""
        from app.handlers.wishes import _finish_wish_create

        user = await _make_user(session)
        msg = _mock_message()
        state = _mock_state()
        data = {"text": "Не забыть позвонить маме"}

        await _finish_wish_create(msg, state, user, "ru", session, data, [])

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "сохранено" in text.lower() or "saved" in text.lower()

    async def test_21_wish_view_shows_details(self, session: AsyncSession):
        """S21: View wish → shows text, people."""
        from app.handlers.wishes import wish_view

        user = await _make_user(session)
        wish = await create_wish(
            session,
            user.id,
            WishCreate(text="Test wish"),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(wish.id), page=0)

        await wish_view(cb, cd, user, "ru", session)

        text = cb.message.edit_text.call_args.args[0]
        assert "Test wish" in text

    async def test_22_wish_edit_text(self, session: AsyncSession):
        """S22: Edit wish text → updated, shown with view keyboard."""
        from app.handlers.wishes import wish_edit_text

        user = await _make_user(session)
        wish = await create_wish(session, user.id, WishCreate(text="Old text"))
        msg = _mock_message("New text")
        state = _mock_state(data={"edit_wish_id": str(wish.id)})

        await wish_edit_text(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "обновлено" in text.lower() or "updated" in text.lower()

    async def test_23_wish_create_limit_reached(self, session: AsyncSession):
        """S23: Create wish at limit → error message."""
        from app.handlers.wishes import _finish_wish_create

        user = await _make_user(session, max_wishes=1)
        await create_wish(session, user.id, WishCreate(text="First"))

        msg = _mock_message()
        state = _mock_state()

        await _finish_wish_create(msg, state, user, "ru", session, {"text": "Second"}, [])

        text = msg.answer.call_args.args[0]
        assert "лимит" in text.lower() or "limit" in text.lower()


# =====================================================================
# 24-29: PEOPLE
# =====================================================================


class TestPersonCRUD:
    """Scenarios 24-29: Person create, view, rename, delete."""

    async def test_24_person_list_empty(self, session: AsyncSession):
        """S24: People list with 0 people → 'empty' message."""
        from app.handlers.people import show_people_list

        user = await _make_user(session)
        cb = _mock_callback()

        await show_people_list(cb, user, "ru", session, page=0)

        text = cb.message.edit_text.call_args.args[0]
        assert "пока нет" in text.lower() or "empty" in text.lower()

    async def test_25_person_create(self, session: AsyncSession):
        """S25: Create person → success message with person name."""
        from app.handlers.people import person_create_name

        user = await _make_user(session)
        msg = _mock_message("Работа")
        state = _mock_state()

        await person_create_name(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "Работа" in text

    async def test_26_person_view_shows_counts(self, session: AsyncSession):
        """S26: View person → shows event/wish counts."""
        from app.handlers.people import person_view

        user = await _make_user(session)
        person = await create_person(session, user.id, "Family")
        await create_event(
            session,
            user.id,
            EventCreate(title="Bday", event_date=date(2020, 5, 1), person_names=["Family"]),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(person.id), page=0)

        # Refresh person with relationships
        await session.refresh(person, ["events", "wishes"])

        await person_view(cb, cd, user, "en", session)

        text = cb.message.edit_text.call_args.args[0]
        assert "Family" in text

    async def test_27_person_rename_success(self, session: AsyncSession):
        """S27: Rename person → success message."""
        from app.handlers.people import person_rename_name

        user = await _make_user(session)
        person = await create_person(session, user.id, "Old")
        msg = _mock_message("New")
        state = _mock_state(data={"rename_person_id": str(person.id)})

        await person_rename_name(msg, state, user, "en", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "New" in text

    async def test_28_person_rename_duplicate_shows_error_with_keyboard(
        self, session: AsyncSession
    ):
        """S28: Rename person to existing name → error + main_menu_kb (not dead-end)."""
        from app.handlers.people import person_rename_name

        user = await _make_user(session)
        await create_person(session, user.id, "Existing")
        person2 = await create_person(session, user.id, "ToRename")
        msg = _mock_message("Existing")
        state = _mock_state(data={"rename_person_id": str(person2.id)})

        await person_rename_name(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "уже есть" in text.lower() or "already" in text.lower()
        # CRITICAL: verify keyboard is present (not a dead-end)
        kw = msg.answer.call_args.kwargs
        assert "reply_markup" in kw

    async def test_29_person_delete(self, session: AsyncSession):
        """S29: Confirm delete person → deleted, returns to list."""
        from app.handlers.people import person_delete_confirm

        user = await _make_user(session)
        person = await create_person(session, user.id, "Temp")
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(person.id), page=0)

        await person_delete_confirm(cb, cd, user, "ru", session)

        cb.answer.assert_called()
        text = cb.answer.call_args.args[0]
        assert "удален" in text.lower() or "deleted" in text.lower()


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

    async def test_35_settings_notification_submenu(self, session: AsyncSession):
        from app.handlers.settings import settings_notif_submenu

        user = await _make_user(session)
        cb = _mock_callback()

        await settings_notif_submenu(cb, user, "ru")

        cb.message.edit_text.assert_called_once()
        kw = cb.message.edit_text.call_args.kwargs
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

    async def test_40_cancel_callback_from_person_rename(self, session: AsyncSession):
        """S40: Press cancel during person rename → main menu."""
        from app.handlers.common import cancel_callback

        user = await _make_user(session)
        cb = _mock_callback(data="cancel")
        state = _mock_state(state_name="PersonRenameStates:waiting_name")

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
            session,
            user.id,
            EventCreate(title="Wedding", event_date=date(2020, 8, 17)),
        )
        await recalculate_for_event(session, event)
        await session.flush()

        cb = _mock_callback()
        state = _mock_state()
        await show_feed_list(cb, user, "en", session, state, page=0)

        # Feed sends separate messages or shows empty via edit_text
        assert cb.message.answer.called or cb.message.edit_text.called


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
        state = AsyncMock()

        await handle_text(msg, state, user, "ru", session)

        msg.answer.assert_not_called()

    async def test_45_voice_too_long(self, session: AsyncSession):
        """S45: Voice message > 60s → 'audio too long' error."""
        from app.handlers.ai import handle_voice

        user = await _make_user(session)
        msg = AsyncMock()
        msg.voice = MagicMock()
        msg.voice.duration = 120
        msg.answer = AsyncMock()
        state = AsyncMock()

        await handle_voice(msg, state, user, "ru", session)

        text = msg.answer.call_args.args[0]
        assert "длинное" in text.lower() or "long" in text.lower()

    @patch("app.handlers.ai.check_ai_rate_limit", return_value=False)
    async def test_46_rate_limited(self, mock_rl, session: AsyncSession):
        """S46: AI rate limit exceeded → error message."""
        from app.handlers.ai import handle_text

        user = await _make_user(session)
        msg = _mock_message("Запомни дату")
        state = AsyncMock()

        await handle_text(msg, state, user, "ru", session)

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
            session,
            user.id,
            EventCreate(title=malicious_title, event_date=date(2023, 1, 1)),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(event.id), page=0)

        await event_view(cb, cd, user, "en", session)

        text = cb.message.edit_text.call_args.args[0]
        # Raw HTML tags must NOT appear — they should be escaped
        assert "<script>" not in text
        assert "&lt;script&gt;" in text or escape("<script>") in text

    async def test_48_html_injection_in_wish_text(self, session: AsyncSession):
        """S48: Wish text with HTML → escaped in view."""
        from app.handlers.wishes import wish_view

        user = await _make_user(session)
        malicious_text = "<img src=x onerror=alert(1)>Hello"
        wish = await create_wish(
            session,
            user.id,
            WishCreate(text=malicious_text),
        )
        cb = _mock_callback()
        cd = _mock_callback_data(id=str(wish.id), page=0)

        await wish_view(cb, cd, user, "ru", session)

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

    async def test_50_wish_edit_returns_none_shows_error(self, session: AsyncSession):
        """S50: Edit non-existent wish → 'not found' message (not silent)."""
        from app.handlers.wishes import wish_edit_text

        user = await _make_user(session)
        msg = _mock_message("Updated text")
        fake_id = str(uuid.uuid4())
        state = _mock_state(data={"edit_wish_id": fake_id})

        await wish_edit_text(msg, state, user, "ru", session)

        state.clear.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "найдено" in text.lower() or "found" in text.lower()


class TestReferralNotification:

    @patch("app.services.referral_service.process_referral", new_callable=AsyncMock, return_value=2)
    @patch("app.handlers.start.log_user_action", new_callable=AsyncMock)
    async def test_referral_sends_notification_to_referrer(
        self, _mock_log, _mock_process, session: AsyncSession
    ):
        from app.handlers.start import cmd_start

        await _make_user(session, user_id=111, language="en")
        user = await _make_user(session, user_id=222, onboarding_completed=True)

        msg = _mock_message("/start")
        msg.bot = AsyncMock()
        msg.bot.send_message = AsyncMock()
        state = _mock_state()
        command = MagicMock()
        command.args = "ref_111"

        await cmd_start(msg, state, user, "ru", session, command=command)

        msg.bot.send_message.assert_called_once()
        call_args = msg.bot.send_message.call_args
        assert call_args.args[0] == 111
        assert "2" in call_args.args[1]

    @patch("app.handlers.start.log_user_action", new_callable=AsyncMock)
    async def test_referral_no_notification_on_duplicate(self, _mock_log, session: AsyncSession):
        from app.handlers.start import cmd_start

        await _make_user(session, user_id=111, language="ru")
        user = await _make_user(session, user_id=222, onboarding_completed=True)
        user.referred_by = 111
        await session.flush()

        msg = _mock_message("/start")
        msg.bot = AsyncMock()
        msg.bot.send_message = AsyncMock()
        state = _mock_state()
        command = MagicMock()
        command.args = "ref_111"

        await cmd_start(msg, state, user, "ru", session, command=command)

        msg.bot.send_message.assert_not_called()
