"""Tests for UX Round 2 features:

1. Onboarding skip creates registration event (no "quick_event" button)
2. Feed card without counter
3. existing_people passed to LLM pipeline
4. Processing message during onboarding voice
5. Improved wish selection with context
6. Edit wishes button text (plural)
7. Build card structure (navigation, wish section)
8. Build step2 text helper
"""

import re
import uuid
from contextlib import contextmanager
from datetime import date
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.i18n.loader import t
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import get_or_create_user


async def _make_user(
    session: AsyncSession,
    user_id: int = 55555,
    onboarding_completed: bool = True,
    **overrides,
) -> User:
    data = UserCreate(id=user_id, username="ux_tester", first_name="UX")
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
    msg.answer.return_value = AsyncMock()
    msg.bot = AsyncMock()
    msg.chat = MagicMock()
    msg.chat.id = 123
    return msg


def _mock_callback() -> AsyncMock:
    cb = AsyncMock()
    cb.data = "noop"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.message.answer_photo = AsyncMock()
    cb.message.delete = AsyncMock()
    cb.message.chat = MagicMock()
    cb.message.chat.id = 123
    cb.bot = AsyncMock()
    return cb


def _mock_state(data: dict | None = None) -> AsyncMock:
    st = AsyncMock()
    st.get_state = AsyncMock(return_value=None)
    st.get_data = AsyncMock(return_value=data or {})
    st.set_state = AsyncMock()
    st.update_data = AsyncMock()
    st.clear = AsyncMock()
    return st


def _mock_voice_message() -> AsyncMock:
    msg = AsyncMock()
    msg.voice = MagicMock()
    msg.voice.file_id = "voice_file_123"
    msg.voice.duration = 5
    msg.text = None
    msg.bot = AsyncMock()
    msg.chat = MagicMock()
    msg.chat.id = 123

    mock_file = MagicMock()
    mock_file.file_path = "voice/file_0.oga"
    msg.bot.get_file = AsyncMock(return_value=mock_file)
    msg.bot.download_file = AsyncMock(return_value=BytesIO(b"\x00" * 1024))

    processing_msg = AsyncMock()
    processing_msg.edit_text = AsyncMock()
    processing_msg.delete = AsyncMock()
    msg.answer = AsyncMock(return_value=processing_msg)

    return msg


def _make_bd_mock(**overrides) -> MagicMock:
    bd = MagicMock()
    bd.id = overrides.get("id", uuid.uuid4())
    bd.event_id = overrides.get("event_id", uuid.uuid4())
    bd.label_ru = overrides.get("label_ru", "1000 дней")
    bd.label_en = overrides.get("label_en", "1000 days")
    bd.target_date = overrides.get("target_date", date(2026, 6, 1))
    bd.event = MagicMock()
    bd.event.title = overrides.get("event_title", "Wedding")
    bd.event.people = overrides.get("people", [])
    bd.event.user_id = overrides.get("user_id", 55555)
    return bd


def _make_wishes(*texts: str) -> list[MagicMock]:
    result = []
    for text in texts:
        w = MagicMock()
        w.text = text
        result.append(w)
    return result


@contextmanager
def _mock_wish_llm(response_content: str = "1", *, side_effect=None):
    with (
        patch("app.handlers.feed.settings") as mock_settings,
        patch("langchain_openai.ChatOpenAI") as mock_llm_cls,
    ):
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o-mini"
        mock_llm = AsyncMock()
        if side_effect:
            mock_llm.ainvoke = AsyncMock(side_effect=side_effect)
        else:
            mock_response = MagicMock()
            mock_response.content = response_content
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm
        yield mock_llm


# =====================================================================
# 1. ONBOARDING SKIP CREATES REGISTRATION EVENT
# =====================================================================


class TestOnboardingSkipCreatesEvent:

    def test_onboarding_event_kb_has_only_skip_ru(self):
        from app.keyboards.main_menu import onboarding_event_kb
        kb = onboarding_event_kb("ru")
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 1
        assert "skip" in all_buttons[0].callback_data

    def test_onboarding_event_kb_has_only_skip_en(self):
        from app.keyboards.main_menu import onboarding_event_kb
        kb = onboarding_event_kb("en")
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 1
        assert "skip" in all_buttons[0].callback_data

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_skip_event_sets_state_and_event_created_ru(self, mock_recalc, session: AsyncSession):
        from app.handlers.start import onboarding_skip_event
        from app.handlers.states import OnboardingStates

        user = await _make_user(session, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_event(cb, state, user, session)

        state.update_data.assert_any_call(event_created=True)
        state.set_state.assert_called_once_with(OnboardingStates.waiting_first_wish)

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_skip_event_sets_state_and_event_created_en(self, mock_recalc, session: AsyncSession):
        from app.handlers.start import onboarding_skip_event
        from app.handlers.states import OnboardingStates

        user = await _make_user(session, user_id=55556, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "en"})

        await onboarding_skip_event(cb, state, user, session)

        state.set_state.assert_called_once_with(OnboardingStates.waiting_first_wish)
        state.update_data.assert_any_call(event_created=True)

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_skip_event_edits_message_with_skipped_text(self, mock_recalc, session: AsyncSession):
        from app.handlers.start import onboarding_skip_event

        user = await _make_user(session, user_id=55557, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_event(cb, state, user, session)

        cb.message.edit_text.assert_called_once_with(t("onboarding.skipped", "ru"))

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_skip_event_shows_step2_with_skip_kb(self, mock_recalc, session: AsyncSession):
        from app.handlers.start import _build_step2_text, onboarding_skip_event

        user = await _make_user(session, user_id=55558, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_event(cb, state, user, session)

        cb.message.answer.assert_called_once()
        call_args = cb.message.answer.call_args
        expected_text = _build_step2_text("ru", ["Личное"])
        assert call_args.args[0] == expected_text
        assert "reply_markup" in call_args.kwargs

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_skip_event_calls_recalculate(self, mock_recalc, session: AsyncSession):
        from app.handlers.start import onboarding_skip_event

        user = await _make_user(session, user_id=55559, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_event(cb, state, user, session)

        mock_recalc.assert_called_once()

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_skip_then_skip_wish_completes_onboarding(self, mock_recalc, session: AsyncSession):
        from app.handlers.start import onboarding_skip_event, onboarding_skip_wish

        user = await _make_user(session, user_id=55563, onboarding_completed=False)

        cb1 = _mock_callback()
        state = _mock_state(data={"lang": "ru"})
        await onboarding_skip_event(cb1, state, user, session)

        state2 = _mock_state(data={"lang": "ru", "event_created": True})
        cb2 = _mock_callback()
        await onboarding_skip_wish(cb2, state2, user, session)

        state2.clear.assert_called_once()


# =====================================================================
# 2. FEED CARD WITHOUT COUNTER
# =====================================================================


_SHARE_UUID = uuid.uuid4()


class TestFeedCardNoCounter:

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_returns_image_bytes(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock()
        image_bytes, _caption, _kb = await _build_card(bd, 5, 100, "ru", AsyncMock(), 55555)

        assert image_bytes == b"fake"
        mock_img.assert_called_once()

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_no_counter_in_caption(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock()
        _image, caption, _kb = await _build_card(bd, 3, 50, "en", AsyncMock(), 55555)

        assert not re.search(r"\d+\s+of\s+\d+", caption)

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_image_gets_label_ru(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock(label_ru="500 дней")
        await _build_card(bd, 0, 1, "ru", AsyncMock(), 55555)

        assert mock_img.call_args.kwargs["label"] == "500 дней"

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_image_gets_label_en(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock(label_en="500 days")
        await _build_card(bd, 0, 1, "en", AsyncMock(), 55555)

        assert mock_img.call_args.kwargs["label"] == "500 days"

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_image_gets_event_title(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock(event_title="Wedding")
        await _build_card(bd, 0, 1, "ru", AsyncMock(), 55555)

        assert mock_img.call_args.kwargs["event_title"] == "Wedding"


# =====================================================================
# 3. EXISTING PEOPLE IN LLM PIPELINE
# =====================================================================


class TestExistingPeopleInPipeline:

    def test_agent_state_has_existing_people_field(self):
        state = AgentState()
        assert hasattr(state, "existing_people")
        assert state.existing_people == []

    def test_agent_state_existing_people_default_factory(self):
        s1 = AgentState()
        s2 = AgentState()
        assert s1.existing_people is not s2.existing_people

    def test_agent_state_existing_people_set(self):
        state = AgentState(existing_people=["Max", "Leva"])
        assert state.existing_people == ["Max", "Leva"]

    def test_event_agent_prompt_has_placeholder(self):
        from app.agents.prompts import EVENT_AGENT_SYSTEM
        assert "{existing_people_block}" in EVENT_AGENT_SYSTEM

    def test_wish_agent_prompt_has_placeholder(self):
        from app.agents.prompts import WISH_AGENT_SYSTEM
        assert "{existing_people_block}" in WISH_AGENT_SYSTEM

    def test_event_agent_prompt_formats_without_people(self):
        from app.agents.prompts import EVENT_AGENT_SYSTEM
        formatted = EVENT_AGENT_SYSTEM.format(
            today="2026-03-06", existing_people_block="",
        )
        assert "{existing_people_block}" not in formatted
        assert "IMPORTANT: The user already has" not in formatted

    def test_event_agent_prompt_formats_with_people(self):
        from app.agents.prompts import EVENT_AGENT_SYSTEM
        block = (
            "\nIMPORTANT: The user already has these people saved: [Max, Leva]. "
            "If the message mentions a name that is similar to one of these "
            "(e.g. spelling variation, transliteration difference like "
            "Дэйзи/Дейзи, or diminutive), use the EXISTING name exactly as written above."
        )
        formatted = EVENT_AGENT_SYSTEM.format(
            today="2026-03-06", existing_people_block=block,
        )
        assert "Max, Leva" in formatted

    def test_wish_agent_prompt_formats_with_people(self):
        from app.agents.prompts import WISH_AGENT_SYSTEM
        block = (
            "\nIMPORTANT: The user already has these people saved: [Daisy]. "
            "If the message mentions a name that is similar..."
        )
        formatted = WISH_AGENT_SYSTEM.format(existing_people_block=block)
        assert "Daisy" in formatted

    @patch("app.handlers.ai._handle_agent_result", new_callable=AsyncMock)
    @patch("app.handlers.ai.process_message", new_callable=AsyncMock)
    @patch("app.handlers.ai.get_user_people", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_handle_text_passes_existing_people(
        self, mock_rate, mock_log, mock_people, mock_process, mock_handle,
    ):
        from app.handlers.ai import handle_text

        person1 = MagicMock()
        person1.name = "Max"
        person2 = MagicMock()
        person2.name = "Leva"
        mock_people.return_value = [person1, person2]
        mock_process.return_value = AgentState(intent="create_wish", wish_text="test")

        msg = _mock_message("Лева хочет наушники")
        user = MagicMock(id=12345)
        session = AsyncMock()

        await handle_text(msg, user, "ru", session)

        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["existing_people"] == ["Max", "Leva"]

    @patch("app.handlers.ai._handle_agent_result", new_callable=AsyncMock)
    @patch("app.handlers.ai.process_message", new_callable=AsyncMock)
    @patch("app.handlers.ai.transcribe_audio", new_callable=AsyncMock, return_value="test voice")
    @patch("app.handlers.ai.get_user_people", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_handle_voice_passes_existing_people(
        self, mock_rate, mock_log, mock_people, mock_transcribe, mock_process, mock_handle,
    ):
        from app.handlers.ai import handle_voice

        person = MagicMock()
        person.name = "Daisy"
        mock_people.return_value = [person]
        mock_process.return_value = AgentState(intent="create_event")

        msg = _mock_voice_message()
        user = MagicMock(id=12345)
        session = AsyncMock()

        await handle_voice(msg, user, "ru", session)

        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["existing_people"] == ["Daisy"]

    @patch("app.handlers.ai._handle_agent_result", new_callable=AsyncMock)
    @patch("app.handlers.ai.process_message", new_callable=AsyncMock)
    @patch("app.handlers.ai.get_user_people", new_callable=AsyncMock, return_value=[])
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_handle_text_empty_people_passes_empty_list(
        self, mock_rate, mock_log, mock_people, mock_process, mock_handle,
    ):
        from app.handlers.ai import handle_text

        mock_process.return_value = AgentState(intent="help")

        msg = _mock_message("help")
        user = MagicMock(id=12345)
        session = AsyncMock()

        await handle_text(msg, user, "en", session)

        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["existing_people"] == []

    async def test_process_message_passes_existing_people_to_graph(self):
        from app.agents.graph import process_message

        with patch("app.agents.graph.get_graph") as mock_graph:
            mock_compiled = AsyncMock()
            mock_compiled.ainvoke = AsyncMock(return_value={
                "intent": "help", "user_language": "ru", "existing_people": ["Max"],
            })
            mock_graph.return_value = mock_compiled

            await process_message(text="test", user_id=1, existing_people=["Max"])

            invoke_args = mock_compiled.ainvoke.call_args[0][0]
            assert invoke_args.existing_people == ["Max"]

    async def test_process_message_none_people_becomes_empty(self):
        from app.agents.graph import process_message

        with patch("app.agents.graph.get_graph") as mock_graph:
            mock_compiled = AsyncMock()
            mock_compiled.ainvoke = AsyncMock(return_value={
                "intent": "help", "user_language": "ru", "existing_people": [],
            })
            mock_graph.return_value = mock_compiled

            await process_message(text="test", user_id=1, existing_people=None)

            invoke_args = mock_compiled.ainvoke.call_args[0][0]
            assert invoke_args.existing_people == []

    async def test_existing_people_loaded_from_db(self, session: AsyncSession):
        from app.services.person_service import create_person, get_user_people

        user = await _make_user(session, user_id=55570)
        await create_person(session, user.id, "Max")
        await create_person(session, user.id, "Daisy")

        people = await get_user_people(session, user.id)
        names = [x.name for x in people]

        assert "Max" in names
        assert "Daisy" in names


# =====================================================================
# 4. PROCESSING MESSAGE DURING ONBOARDING VOICE
# =====================================================================


class TestOnboardingVoiceProcessing:

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value="свадьба завтра")
    @patch("app.agents.graph.process_message", new_callable=AsyncMock)
    @patch("app.services.event_service.create_event", new_callable=AsyncMock)
    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_event_voice_shows_processing_message(
        self, mock_recalc, mock_create, mock_process, mock_transcribe,
        session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_event_voice

        mock_event = MagicMock(title="Wedding")
        mock_create.return_value = mock_event
        mock_process.return_value = AgentState(
            intent="create_event", event_title="Wedding",
            event_date=date(2026, 3, 7), person_names=[],
        )

        user = await _make_user(session, user_id=55580, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_event_voice(msg, state, user, session)

        first_call_text = msg.answer.call_args_list[0].args[0]
        assert first_call_text == t("ai.processing", "ru")

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value=None)
    async def test_event_voice_deletes_processing_on_transcription_fail(
        self, mock_transcribe, session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_event_voice

        user = await _make_user(session, user_id=55581, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_event_voice(msg, state, user, session)

        processing_msg = msg.answer.return_value
        processing_msg.delete.assert_called_once()

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value="свадьба завтра")
    @patch("app.agents.graph.process_message", new_callable=AsyncMock)
    @patch("app.services.event_service.create_event", new_callable=AsyncMock)
    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_event_voice_edits_processing_on_success(
        self, mock_recalc, mock_create, mock_process, mock_transcribe,
        session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_event_voice

        mock_event = MagicMock(title="Wedding")
        mock_create.return_value = mock_event
        mock_process.return_value = AgentState(
            intent="create_event", event_title="Wedding",
            event_date=date(2026, 3, 7), person_names=[],
        )

        user = await _make_user(session, user_id=55582, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_event_voice(msg, state, user, session)

        processing_msg = msg.answer.return_value
        processing_msg.edit_text.assert_called_once()
        edit_text = processing_msg.edit_text.call_args.args[0]
        assert t("events.created", "ru", title="Wedding") == edit_text

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value="свадьба завтра")
    @patch("app.agents.graph.process_message", new_callable=AsyncMock)
    async def test_event_voice_edits_processing_on_ai_failure(
        self, mock_process, mock_transcribe, session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_event_voice

        mock_process.return_value = AgentState(
            intent="help", event_title="", event_date=None,
        )

        user = await _make_user(session, user_id=55583, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_event_voice(msg, state, user, session)

        processing_msg = msg.answer.return_value
        processing_msg.edit_text.assert_called_once()
        edit_text = processing_msg.edit_text.call_args.args[0]
        assert edit_text == t("ai.not_understood", "ru")

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value="свадьба завтра")
    @patch("app.agents.graph.process_message", new_callable=AsyncMock, side_effect=RuntimeError("API error"))
    async def test_event_voice_edits_processing_on_exception(
        self, mock_process, mock_transcribe, session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_event_voice

        user = await _make_user(session, user_id=55584, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_event_voice(msg, state, user, session)

        processing_msg = msg.answer.return_value
        processing_msg.edit_text.assert_called_once()
        edit_text = processing_msg.edit_text.call_args.args[0]
        assert edit_text == t("ai.not_understood", "ru")

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value="хочу наушники")
    @patch("app.handlers.start._create_wish_via_ai", new_callable=AsyncMock, return_value=True)
    @patch("app.handlers.start.update_user", new_callable=AsyncMock)
    @patch("app.handlers.start.log_user_action", new_callable=AsyncMock)
    async def test_wish_voice_shows_processing_message(
        self, mock_log, mock_update, mock_create, mock_transcribe,
        session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_wish_voice

        user = await _make_user(session, user_id=55585, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_wish_voice(msg, state, user, session)

        first_call_text = msg.answer.call_args_list[0].args[0]
        assert first_call_text == t("ai.processing", "ru")

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value=None)
    async def test_wish_voice_deletes_processing_on_transcription_fail(
        self, mock_transcribe, session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_wish_voice

        user = await _make_user(session, user_id=55586, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_wish_voice(msg, state, user, session)

        processing_msg = msg.answer.return_value
        processing_msg.delete.assert_called_once()

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value="хочу наушники")
    @patch("app.handlers.start._create_wish_via_ai", new_callable=AsyncMock, return_value=True)
    @patch("app.handlers.start.update_user", new_callable=AsyncMock)
    @patch("app.handlers.start.log_user_action", new_callable=AsyncMock)
    async def test_wish_voice_edits_processing_on_success(
        self, mock_log, mock_update, mock_create, mock_transcribe,
        session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_wish_voice

        user = await _make_user(session, user_id=55587, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_wish_voice(msg, state, user, session)

        processing_msg = msg.answer.return_value
        processing_msg.edit_text.assert_called_once()
        edit_text = processing_msg.edit_text.call_args.args[0]
        assert edit_text == t("wishes.created", "ru")

    @patch("app.handlers.start._transcribe_voice", new_callable=AsyncMock, return_value="хочу наушники")
    @patch("app.handlers.start._create_wish_via_ai", new_callable=AsyncMock, side_effect=RuntimeError("API error"))
    async def test_wish_voice_edits_processing_on_exception(
        self, mock_create, mock_transcribe, session: AsyncSession,
    ):
        from app.handlers.start import onboarding_first_wish_voice

        user = await _make_user(session, user_id=55588, onboarding_completed=False)
        msg = _mock_voice_message()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_first_wish_voice(msg, state, user, session)

        processing_msg = msg.answer.return_value
        processing_msg.edit_text.assert_called_once()
        edit_text = processing_msg.edit_text.call_args.args[0]
        assert edit_text == t("ai.not_understood", "ru")


# =====================================================================
# 5. IMPROVED WISH SELECTION WITH CONTEXT
# =====================================================================


class TestImprovedWishSelection:

    async def test_no_wishes_returns_none(self):
        from app.handlers.feed import _select_best_wish
        assert await _select_best_wish([], "1000 days") is None

    async def test_single_wish_returns_it(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("Buy flowers")
        assert await _select_best_wish(wishes, "1000 days") == "Buy flowers"

    async def test_no_api_key_returns_first(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("First", "Second")
        with patch("app.handlers.feed.settings") as mock_settings:
            mock_settings.openai_api_key = None
            assert await _select_best_wish(wishes, "label") == "First"

    async def test_single_wish_with_context_params(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("Single")
        result = await _select_best_wish(
            wishes, "500 days",
            event_title="Wedding",
            target_date_str="15 июня 2026",
            relative_date_str="через 3 месяца",
        )
        assert result == "Single"

    async def test_llm_prompt_includes_context(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("Buy flowers", "Buy chocolates")

        with _mock_wish_llm("1") as mock_llm:
            await _select_best_wish(
                wishes, "1000 days",
                event_title="Wedding",
                target_date_str="15 июня 2026",
                relative_date_str="через 3 месяца",
            )

            user_msg = mock_llm.ainvoke.call_args[0][0][1]["content"]
            assert "Wedding" in user_msg
            assert "15 июня 2026" in user_msg
            assert "через 3 месяца" in user_msg
            assert "1000 days" in user_msg

    async def test_llm_picks_first(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("First", "Second")
        with _mock_wish_llm("1"):
            assert await _select_best_wish(wishes, "label") == "First"

    async def test_llm_picks_second(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("First", "Second")
        with _mock_wish_llm("2"):
            assert await _select_best_wish(wishes, "label") == "Second"

    async def test_llm_returns_zero_falls_to_first(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("First", "Second")
        with _mock_wish_llm("0"):
            assert await _select_best_wish(wishes, "label") == "First"

    async def test_llm_returns_text_falls_to_first(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("First", "Second")
        with _mock_wish_llm("The best option is number 1"):
            assert await _select_best_wish(wishes, "label") == "First"

    async def test_llm_returns_out_of_range_falls_to_first(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("Only", "Two")
        with _mock_wish_llm("99"):
            assert await _select_best_wish(wishes, "label") == "Only"

    async def test_llm_error_falls_to_first(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("First", "Second")
        with _mock_wish_llm(side_effect=RuntimeError("API down")):
            assert await _select_best_wish(wishes, "label") == "First"

    async def test_llm_truncates_long_text(self):
        from app.handlers.feed import _select_best_wish
        wishes = _make_wishes("A" * 500, "Short")

        with _mock_wish_llm("1") as mock_llm:
            await _select_best_wish(wishes, "label")

            user_msg = mock_llm.ainvoke.call_args[0][0][1]["content"]
            assert "A" * 201 not in user_msg

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed._select_best_wish", new_callable=AsyncMock, return_value="Best wish")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock)
    async def test_build_card_passes_context_to_selector(self, mock_wishes, mock_selector, mock_img, mock_share):
        from app.handlers.feed import _build_card

        person = MagicMock(name="Max")
        bd = _make_bd_mock(
            event_title="Wedding",
            people=[person],
            target_date=date(2026, 6, 1),
        )
        mock_wishes.return_value = [MagicMock(text="gift")]
        mock_session = AsyncMock()

        _image, _caption, _kb = await _build_card(bd, 0, 1, "ru", mock_session, 55555)

        mock_selector.assert_called_once()
        call_kwargs = mock_selector.call_args.kwargs
        assert call_kwargs["event_title"] == "Wedding"
        assert call_kwargs["target_date_str"]
        assert call_kwargs["relative_date_str"]


# =====================================================================
# 6. EDIT WISHES BUTTON TEXT (PLURAL)
# =====================================================================


class TestEditWishesButtonPlural:

    def test_ru_is_plural(self):
        text = t("events.edit_wish", "ru")
        assert "желания" in text.lower()
        assert "желание" not in text.lower()

    def test_en_is_plural(self):
        text = t("events.edit_wish", "en")
        assert "wishes" in text.lower()

    def test_ru_exact(self):
        assert t("events.edit_wish", "ru") == "Редактировать желания"

    def test_en_exact(self):
        assert t("events.edit_wish", "en") == "Edit wishes"


# =====================================================================
# 7. BUILD CARD STRUCTURE
# =====================================================================


class TestBuildCardStructure:

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_no_people_skips_wish_section(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock(people=[])
        mock_session = AsyncMock()

        _image, caption, _kb = await _build_card(bd, 0, 1, "ru", mock_session, 55555)

        mock_wishes.assert_not_called()
        assert t("feed.wish", "ru") not in caption

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed._select_best_wish", new_callable=AsyncMock, return_value=None)
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_wish_selector_none_omits_wish_text(self, mock_wishes, mock_selector, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock(people=[MagicMock(name="Max")])
        mock_session = AsyncMock()

        _image, caption, _kb = await _build_card(bd, 0, 1, "ru", mock_session, 55555)

        assert t("feed.wish", "ru") not in caption

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_first_page_shows_next_only(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock()
        _image, _caption, kb = await _build_card(bd, 0, 5, "ru", AsyncMock(), 55555)

        nav_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data and "card" in btn.callback_data]
        assert len(nav_cbs) == 1
        assert nav_cbs[0].endswith(":1")

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_middle_page_shows_both_nav(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock()
        _image, _caption, kb = await _build_card(bd, 2, 5, "ru", AsyncMock(), 55555)

        nav_cbs = sorted(btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data and "card" in btn.callback_data)
        assert len(nav_cbs) == 2
        assert nav_cbs[0].endswith(":1")
        assert nav_cbs[1].endswith(":3")

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_last_page_shows_prev_only(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock()
        _image, _caption, kb = await _build_card(bd, 4, 5, "ru", AsyncMock(), 55555)

        nav_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data and "card" in btn.callback_data]
        assert len(nav_cbs) == 1
        assert nav_cbs[0].endswith(":3")

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_single_item_no_nav(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock()
        _image, _caption, kb = await _build_card(bd, 0, 1, "ru", AsyncMock(), 55555)

        nav_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data and "card" in btn.callback_data]
        assert len(nav_cbs) == 0

    @patch("app.handlers.feed.generate_share_uuid", new_callable=AsyncMock, return_value=_SHARE_UUID)
    @patch("app.handlers.feed.generate_share_image", return_value=b"fake")
    @patch("app.handlers.feed.get_wishes_by_person_names", new_callable=AsyncMock, return_value=[])
    async def test_card_always_has_event_wishes_share_back_buttons(self, mock_wishes, mock_img, mock_share):
        from app.handlers.feed import _build_card

        bd = _make_bd_mock()
        _image, _caption, kb = await _build_card(bd, 0, 1, "ru", AsyncMock(), 55555)

        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        all_webapps = [btn.web_app for row in kb.inline_keyboard for btn in row if btn.web_app]
        assert any("view_new" in cb for cb in all_cbs)
        assert any("wishes" in cb for cb in all_cbs)
        assert len(all_webapps) == 1
        assert any("main" in cb for cb in all_cbs)


# =====================================================================
# 8. BUILD STEP2 TEXT
# =====================================================================


class TestBuildStep2Text:

    def test_personal_only_ru(self):
        from app.handlers.start import _build_step2_text
        assert _build_step2_text("ru", ["Личное"]) == t("onboarding.step2_personal", "ru")

    def test_personal_only_en(self):
        from app.handlers.start import _build_step2_text
        assert _build_step2_text("en", ["Personal"]) == t("onboarding.step2_personal", "en")

    def test_real_person_ru(self):
        from app.handlers.start import _build_step2_text
        text = _build_step2_text("ru", ["Max"])
        assert text == t("onboarding.step2_with_person", "ru", name="Max")
        assert "Max" in text

    def test_real_person_en(self):
        from app.handlers.start import _build_step2_text
        text = _build_step2_text("en", ["Daisy"])
        assert text == t("onboarding.step2_with_person", "en", name="Daisy")
        assert "Daisy" in text

    def test_empty_list_falls_to_personal(self):
        from app.handlers.start import _build_step2_text
        assert _build_step2_text("ru", []) == t("onboarding.step2_personal", "ru")

    def test_mixed_names_uses_first_real(self):
        from app.handlers.start import _build_step2_text
        assert "Max" in _build_step2_text("ru", ["Личное", "Max"])


# =====================================================================
# E2E: FULL ONBOARDING SKIP FLOW WITH DB
# =====================================================================


class TestOnboardingSkipE2E:

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_skip_creates_event_with_correct_data_ru(self, mock_recalc, session: AsyncSession):
        from app.handlers.start import onboarding_skip_event
        from app.services.event_service import get_user_events

        user = await _make_user(session, user_id=55600, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "ru"})

        await onboarding_skip_event(cb, state, user, session)

        events = await get_user_events(session, user.id)
        assert len(events) == 1
        assert events[0].title == t("onboarding.quick_event", "ru")
        assert events[0].event_date == date.today()
        assert len(events[0].people) == 1
        assert events[0].people[0].name == "Личное"

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    async def test_skip_creates_event_with_correct_data_en(self, mock_recalc, session: AsyncSession):
        from app.handlers.start import onboarding_skip_event
        from app.services.event_service import get_user_events

        user = await _make_user(session, user_id=55601, onboarding_completed=False)
        cb = _mock_callback()
        state = _mock_state(data={"lang": "en"})

        await onboarding_skip_event(cb, state, user, session)

        events = await get_user_events(session, user.id)
        assert len(events) == 1
        assert events[0].title == t("onboarding.quick_event", "en")
        assert events[0].people[0].name == "Personal"


# =====================================================================
# E2E: EXISTING PEOPLE FLOW WITH DB
# =====================================================================


class TestExistingPeopleE2E:

    async def test_people_loaded_from_db(self, session: AsyncSession):
        from app.services.person_service import create_person, get_user_people

        user = await _make_user(session, user_id=55610)
        await create_person(session, user.id, "Max")
        await create_person(session, user.id, "Дейзи")

        people = await get_user_people(session, user.id)
        names = sorted([x.name for x in people])
        assert names == ["Max", "Дейзи"]

    async def test_event_with_existing_person_reuses_record(self, session: AsyncSession):
        from app.schemas.event import EventCreate
        from app.services.event_service import create_event
        from app.services.person_service import create_person, get_user_people

        user = await _make_user(session, user_id=55611)
        await create_person(session, user.id, "Max")

        event = await create_event(session, user.id, EventCreate(
            title="Party", event_date=date(2026, 1, 1), person_names=["Max"],
        ))

        people = await get_user_people(session, user.id)
        assert len(people) == 1
        assert people[0].name == "Max"
        assert len(event.people) == 1
        assert event.people[0].name == "Max"
