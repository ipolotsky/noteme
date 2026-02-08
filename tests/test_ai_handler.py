"""Tests for AI handler — text/voice processing + _handle_agent_result.

Covers the tag_names bug fix ([] or None → ValidationError), voice handler,
and all intent paths in _handle_agent_result.
"""

import uuid
from datetime import date
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.state import AgentState
from app.handlers.ai import _format_user_text
from app.schemas.event import EventCreate
from app.schemas.note import NoteCreate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user():
    """Create a mock User object."""
    user = MagicMock()
    user.id = 123456789
    user.max_events = 10
    user.max_notes = 10
    return user


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_message():
    """Create a mock Message for text handling."""
    msg = AsyncMock()
    msg.text = "test message"
    msg.answer = AsyncMock()
    msg.bot = AsyncMock()
    return msg


@pytest.fixture
def mock_processing_msg():
    """Create a mock processing message (returned by message.answer)."""
    processing = AsyncMock()
    processing.edit_text = AsyncMock()
    return processing


@pytest.fixture
def mock_voice_message():
    """Create a mock Message with voice."""
    msg = AsyncMock()
    msg.voice = MagicMock()
    msg.voice.file_id = "AgACAgIAAx0CZ"
    msg.voice.duration = 5
    msg.answer = AsyncMock()
    msg.bot = AsyncMock()

    # bot.get_file returns a file object with file_path
    mock_file = MagicMock()
    mock_file.file_path = "voice/file_0.oga"
    msg.bot.get_file = AsyncMock(return_value=mock_file)

    # bot.download_file returns BytesIO with audio data
    audio_data = b"\x00" * 1024  # dummy audio bytes
    msg.bot.download_file = AsyncMock(return_value=BytesIO(audio_data))

    return msg


# =====================================================================
# Pydantic schema validation — the root cause bug
# =====================================================================


class TestTagNamesSchemaValidation:
    """Verify that tag_names=None causes ValidationError (the original bug)."""

    def test_note_create_with_empty_list_ok(self):
        """NoteCreate accepts empty list for tag_names."""
        note = NoteCreate(text="test", tag_names=[])
        assert note.tag_names == []

    def test_note_create_with_tags_ok(self):
        """NoteCreate accepts a populated list."""
        note = NoteCreate(text="test", tag_names=["Max", "gifts"])
        assert note.tag_names == ["Max", "gifts"]

    def test_note_create_with_none_fails(self):
        """NoteCreate rejects None for tag_names — the original bug."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            NoteCreate(text="test", tag_names=None)

    def test_event_create_with_empty_list_ok(self):
        """EventCreate accepts empty list for tag_names."""
        event = EventCreate(title="test", event_date=date(2024, 1, 1), tag_names=[])
        assert event.tag_names == []

    def test_event_create_with_none_fails(self):
        """EventCreate rejects None for tag_names."""
        with pytest.raises(Exception):
            EventCreate(title="test", event_date=date(2024, 1, 1), tag_names=None)

    def test_or_none_vs_or_empty_list(self):
        """Demonstrate the bug: [] or None == None, [] or [] == []."""
        empty_tags = []
        assert (empty_tags or None) is None  # BUG pattern
        assert (empty_tags or []) == []  # FIX pattern

    def test_populated_tags_or_patterns_equivalent(self):
        """When tags are populated, both patterns work the same."""
        tags = ["Max"]
        assert (tags or None) == ["Max"]
        assert (tags or []) == ["Max"]


# =====================================================================
# _format_user_text tests
# =====================================================================


class TestFormatUserText:
    """Test _format_user_text helper for cleaning up user input."""

    def test_capitalizes_first_letter(self):
        assert _format_user_text("hello world") == "Hello world."

    def test_adds_period_if_missing(self):
        assert _format_user_text("Test message") == "Test message."

    def test_keeps_existing_period(self):
        assert _format_user_text("Already has period.") == "Already has period."

    def test_keeps_exclamation(self):
        assert _format_user_text("Wow!") == "Wow!"

    def test_keeps_question_mark(self):
        assert _format_user_text("Really?") == "Really?"

    def test_keeps_ellipsis(self):
        assert _format_user_text("Hmm…") == "Hmm…"

    def test_strips_whitespace(self):
        assert _format_user_text("  hello  ") == "Hello."

    def test_collapses_multiple_spaces(self):
        assert _format_user_text("hello   world") == "Hello world."

    def test_collapses_newlines(self):
        assert _format_user_text("hello\n\nworld") == "Hello world."

    def test_empty_string(self):
        assert _format_user_text("") == ""

    def test_russian_text(self):
        assert _format_user_text("позавчера я познакомился с Левой") == "Позавчера я познакомился с Левой."

    def test_russian_text_with_punctuation(self):
        assert _format_user_text("макс хочет наушники!") == "Макс хочет наушники!"

    def test_voice_transcript_cleanup(self):
        """Voice transcripts often have extra spaces and no punctuation."""
        assert _format_user_text("  ну  вот  вчера я встретился с Максом  ") == "Ну вот вчера я встретился с Максом."


# =====================================================================
# _handle_agent_result tests
# =====================================================================


class TestHandleAgentResult:
    """Test _handle_agent_result with various agent states."""

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_event", new_callable=AsyncMock)
    async def test_create_event_with_empty_tags(
        self, mock_create, mock_recalc, mock_log,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """create_event with empty tag_names should work (was the bug)."""
        from app.handlers.ai import _handle_agent_result

        mock_event = MagicMock()
        mock_event.id = uuid.uuid4()
        mock_event.title = "Wedding"
        mock_event.event_date = date(2022, 8, 17)
        mock_create.return_value = mock_event

        state = AgentState(
            intent="create_event",
            event_title="Wedding",
            event_date=date(2022, 8, 17),
            raw_text="свадьба 17 августа 2022",
            tag_names=[],  # Empty tags — was causing the bug
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        mock_create.assert_called_once()
        # Verify tag_names is [] not None
        call_args = mock_create.call_args
        event_data = call_args[0][2]  # 3rd positional arg: EventCreate
        assert isinstance(event_data, EventCreate)
        assert event_data.tag_names == []
        # Verify raw_text saved as formatted description
        assert event_data.description == "Свадьба 17 августа 2022."

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_event", new_callable=AsyncMock)
    async def test_create_event_with_tags(
        self, mock_create, mock_recalc, mock_log,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """create_event with populated tags works."""
        mock_event = MagicMock()
        mock_event.id = uuid.uuid4()
        mock_event.title = "Wedding with Max"
        mock_event.event_date = date(2022, 8, 17)
        mock_create.return_value = mock_event

        from app.handlers.ai import _handle_agent_result

        state = AgentState(
            intent="create_event",
            event_title="Wedding with Max",
            event_date=date(2022, 8, 17),
            tag_names=["Max", "relationships"],
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        mock_create.assert_called_once()
        event_data = mock_create.call_args[0][2]
        assert event_data.tag_names == ["Max", "relationships"]

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_note", new_callable=AsyncMock)
    async def test_create_note_with_empty_tags(
        self, mock_create, mock_log,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """create_note with empty tag_names should work (was the bug)."""
        from app.handlers.ai import _handle_agent_result

        mock_note = MagicMock()
        mock_note.id = uuid.uuid4()
        mock_create.return_value = mock_note

        state = AgentState(
            intent="create_note",
            note_text="Я хочу книгу От нуля до единицы",
            raw_text="я хочу книгу От нуля до единицы",
            tag_names=[],  # Empty tags — was causing the bug
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        mock_create.assert_called_once()
        note_data = mock_create.call_args[0][2]
        assert isinstance(note_data, NoteCreate)
        assert note_data.tag_names == []
        # Note text should be formatted original text
        assert note_data.text == "Я хочу книгу От нуля до единицы."

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_note", new_callable=AsyncMock)
    async def test_create_note_with_tags(
        self, mock_create, mock_log,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """create_note with populated tags works."""
        from app.handlers.ai import _handle_agent_result

        mock_note = MagicMock()
        mock_note.id = uuid.uuid4()
        mock_create.return_value = mock_note

        state = AgentState(
            intent="create_note",
            note_text="Лева хочет в подарок сникерс",
            tag_names=["Лева", "подарки"],
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        mock_create.assert_called_once()
        note_data = mock_create.call_args[0][2]
        assert note_data.tag_names == ["Лева", "подарки"]

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_note", new_callable=AsyncMock)
    async def test_create_note_with_reminder(
        self, mock_create, mock_log,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """create_note with reminder_date passes it correctly."""
        from app.handlers.ai import _handle_agent_result

        mock_note = MagicMock()
        mock_note.id = uuid.uuid4()
        mock_create.return_value = mock_note

        state = AgentState(
            intent="create_note",
            note_text="Buy present",
            tag_names=["Max"],
            note_reminder_date=date(2026, 12, 25),
            user_language="en",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "en", mock_session,
        )

        note_data = mock_create.call_args[0][2]
        assert note_data.reminder_date == date(2026, 12, 25)

    async def test_create_event_missing_date_no_db_call(
        self, mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """create_event without date falls through to default response."""
        from app.handlers.ai import _handle_agent_result

        state = AgentState(
            intent="create_event",
            event_title="Wedding",
            event_date=None,  # Missing date
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        # Should show fallthrough response, no DB call
        mock_processing_msg.edit_text.assert_called_once()

    async def test_create_note_empty_text_no_db_call(
        self, mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """create_note without text falls through to default response."""
        from app.handlers.ai import _handle_agent_result

        state = AgentState(
            intent="create_note",
            note_text="",  # Empty text
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        mock_processing_msg.edit_text.assert_called_once()

    async def test_view_intents_no_db_call(
        self, mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """View intents just show a response and return."""
        from app.handlers.ai import _handle_agent_result

        for intent in ("view_events", "view_notes", "view_feed", "view_tags"):
            mock_processing_msg.reset_mock()
            state = AgentState(intent=intent, user_language="ru")

            await _handle_agent_result(
                mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
            )

            mock_processing_msg.edit_text.assert_called_once()

    async def test_help_intent_shows_response(
        self, mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """Help intent shows response_text from formatter."""
        from app.handlers.ai import _handle_agent_result

        state = AgentState(
            intent="help",
            response_text="I help with dates and notes.",
            user_language="en",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "en", mock_session,
        )

        mock_processing_msg.edit_text.assert_called_once()
        call_text = mock_processing_msg.edit_text.call_args[0][0]
        assert call_text == "I help with dates and notes."

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_event", new_callable=AsyncMock)
    async def test_event_saves_raw_text_as_description(
        self, mock_create, mock_recalc, mock_log,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """Event description is the formatted original user text."""
        from app.handlers.ai import _handle_agent_result

        mock_event = MagicMock()
        mock_event.id = uuid.uuid4()
        mock_event.title = "Met Leva"
        mock_event.event_date = date(2026, 2, 6)
        mock_create.return_value = mock_event

        state = AgentState(
            intent="create_event",
            event_title="Met Leva",
            event_date=date(2026, 2, 6),
            raw_text="позавчера я познакомился с Левой",
            tag_names=["Лева"],
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        event_data = mock_create.call_args[0][2]
        assert event_data.description == "Позавчера я познакомился с Левой."

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_note", new_callable=AsyncMock)
    async def test_note_saves_formatted_raw_text(
        self, mock_create, mock_log,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """Note text is the formatted original user text."""
        from app.handlers.ai import _handle_agent_result

        mock_note = MagicMock()
        mock_note.id = uuid.uuid4()
        mock_create.return_value = mock_note

        state = AgentState(
            intent="create_note",
            note_text="Лева хочет в подарок сникерс",
            raw_text="лева хочет в подарок сникерс",
            tag_names=["Лева"],
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        note_data = mock_create.call_args[0][2]
        assert note_data.text == "Лева хочет в подарок сникерс."

    @patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_event", new_callable=AsyncMock)
    async def test_event_limit_error(
        self, mock_create, mock_log, mock_recalc,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """EventLimitError shows limit_reached message."""
        from app.handlers.ai import _handle_agent_result
        from app.services.event_service import EventLimitError

        mock_create.side_effect = EventLimitError(10)

        state = AgentState(
            intent="create_event",
            event_title="Too Many",
            event_date=date(2024, 1, 1),
            tag_names=[],
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        call_text = mock_processing_msg.edit_text.call_args[0][0]
        assert "10" in call_text  # limit number in message

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.create_note", new_callable=AsyncMock)
    async def test_note_limit_error(
        self, mock_create, mock_log,
        mock_message, mock_processing_msg, mock_user, mock_session,
    ):
        """NoteLimitError shows limit_reached message."""
        from app.handlers.ai import _handle_agent_result
        from app.services.note_service import NoteLimitError

        mock_create.side_effect = NoteLimitError(10)

        state = AgentState(
            intent="create_note",
            note_text="Too Many Notes",
            tag_names=[],
            user_language="ru",
        )

        await _handle_agent_result(
            mock_message, mock_processing_msg, state, mock_user, "ru", mock_session,
        )

        call_text = mock_processing_msg.edit_text.call_args[0][0]
        assert "10" in call_text


# =====================================================================
# handle_text tests
# =====================================================================


class TestHandleText:
    """Test handle_text handler."""

    @patch("app.handlers.ai._handle_agent_result", new_callable=AsyncMock)
    @patch("app.handlers.ai.process_message", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_text_message_pipeline(
        self, mock_rate, mock_log, mock_process, mock_handle,
        mock_message, mock_user, mock_session,
    ):
        """Text message goes through pipeline and calls _handle_agent_result."""
        from app.handlers.ai import handle_text

        mock_message.text = "Я хочу книгу От нуля до единицы"
        processing_msg = AsyncMock()
        mock_message.answer = AsyncMock(return_value=processing_msg)

        mock_state = AgentState(intent="create_note", note_text="test")
        mock_process.return_value = mock_state

        await handle_text(mock_message, mock_user, "ru", mock_session)

        mock_process.assert_called_once_with(
            text="Я хочу книгу От нуля до единицы",
            user_id=mock_user.id,
            user_language="ru",
        )
        mock_handle.assert_called_once()

    @patch("app.handlers.ai.process_message", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_text_pipeline_exception_shows_error(
        self, mock_rate, mock_log, mock_process,
        mock_message, mock_user, mock_session,
    ):
        """Exception in pipeline shows errors.unknown to user."""
        from app.handlers.ai import handle_text

        mock_message.text = "test"
        processing_msg = AsyncMock()
        mock_message.answer = AsyncMock(return_value=processing_msg)

        mock_process.side_effect = RuntimeError("OpenAI timeout")

        await handle_text(mock_message, mock_user, "ru", mock_session)

        processing_msg.edit_text.assert_called_once()
        # Should contain the error message from i18n
        call_text = processing_msg.edit_text.call_args[0][0]
        assert len(call_text) > 0  # Has some error text

    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=False)
    async def test_rate_limited_text(self, mock_rate, mock_message, mock_user, mock_session):
        """Rate-limited user gets rate_limit message."""
        from app.handlers.ai import handle_text

        mock_message.text = "test"

        await handle_text(mock_message, mock_user, "ru", mock_session)

        mock_message.answer.assert_called_once()

    async def test_skip_commands(self, mock_message, mock_user, mock_session):
        """Messages starting with / are skipped."""
        from app.handlers.ai import handle_text

        mock_message.text = "/start"

        await handle_text(mock_message, mock_user, "ru", mock_session)

        mock_message.answer.assert_not_called()

    async def test_skip_empty_text(self, mock_message, mock_user, mock_session):
        """Empty text messages are skipped."""
        from app.handlers.ai import handle_text

        mock_message.text = None

        await handle_text(mock_message, mock_user, "ru", mock_session)

        mock_message.answer.assert_not_called()


# =====================================================================
# handle_voice tests
# =====================================================================


class TestHandleVoice:
    """Test handle_voice handler."""

    @patch("app.handlers.ai._handle_agent_result", new_callable=AsyncMock)
    @patch("app.handlers.ai.process_message", new_callable=AsyncMock)
    @patch("app.handlers.ai.transcribe_audio", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_voice_full_pipeline(
        self, mock_rate, mock_log, mock_transcribe, mock_process, mock_handle,
        mock_voice_message, mock_user, mock_session,
    ):
        """Voice message downloads, transcribes, processes, and handles result."""
        from app.handlers.ai import handle_voice

        processing_msg = AsyncMock()
        mock_voice_message.answer = AsyncMock(return_value=processing_msg)
        mock_transcribe.return_value = "позавчера я познакомился с Левой"
        mock_state = AgentState(intent="create_event")
        mock_process.return_value = mock_state

        await handle_voice(mock_voice_message, mock_user, "ru", mock_session)

        # Verify file download via message.bot
        mock_voice_message.bot.get_file.assert_called_once_with("AgACAgIAAx0CZ")
        mock_voice_message.bot.download_file.assert_called_once()

        # Verify transcription called with real filename from Telegram
        mock_transcribe.assert_called_once()
        assert mock_transcribe.call_args[1]["user_id"] == mock_user.id
        assert mock_transcribe.call_args[1]["filename"] == "file_0.oga"

        # Verify pipeline called with transcribed text
        mock_process.assert_called_once_with(
            text="позавчера я познакомился с Левой",
            user_id=mock_user.id,
            user_language="ru",
            is_voice=True,
        )

        mock_handle.assert_called_once()

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_voice_too_long(
        self, mock_rate, mock_log,
        mock_voice_message, mock_user, mock_session,
    ):
        """Voice > 60s gets audio_too_long message."""
        from app.handlers.ai import handle_voice

        mock_voice_message.voice.duration = 120  # 2 minutes

        await handle_voice(mock_voice_message, mock_user, "ru", mock_session)

        mock_voice_message.answer.assert_called_once()

    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=False)
    async def test_voice_rate_limited(self, mock_rate, mock_voice_message, mock_user, mock_session):
        """Rate-limited voice gets rate_limit message."""
        from app.handlers.ai import handle_voice

        await handle_voice(mock_voice_message, mock_user, "ru", mock_session)

        mock_voice_message.answer.assert_called_once()

    @patch("app.handlers.ai.transcribe_audio", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_voice_empty_transcription(
        self, mock_rate, mock_log, mock_transcribe,
        mock_voice_message, mock_user, mock_session,
    ):
        """Empty transcription shows audio_empty message."""
        from app.handlers.ai import handle_voice

        processing_msg = AsyncMock()
        mock_voice_message.answer = AsyncMock(return_value=processing_msg)
        mock_transcribe.return_value = "   "  # whitespace only

        await handle_voice(mock_voice_message, mock_user, "ru", mock_session)

        processing_msg.edit_text.assert_called_once()

    @patch("app.handlers.ai.transcribe_audio", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_voice_transcription_error(
        self, mock_rate, mock_log, mock_transcribe,
        mock_voice_message, mock_user, mock_session,
    ):
        """Exception during transcription shows errors.unknown."""
        from app.handlers.ai import handle_voice

        processing_msg = AsyncMock()
        mock_voice_message.answer = AsyncMock(return_value=processing_msg)
        mock_transcribe.side_effect = RuntimeError("Whisper API error")

        await handle_voice(mock_voice_message, mock_user, "ru", mock_session)

        processing_msg.edit_text.assert_called_once()

    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_voice_download_error(
        self, mock_rate, mock_log,
        mock_voice_message, mock_user, mock_session,
    ):
        """Exception during file download shows errors.unknown."""
        from app.handlers.ai import handle_voice

        processing_msg = AsyncMock()
        mock_voice_message.answer = AsyncMock(return_value=processing_msg)
        mock_voice_message.bot.get_file.side_effect = RuntimeError("Telegram API error")

        await handle_voice(mock_voice_message, mock_user, "ru", mock_session)

        processing_msg.edit_text.assert_called_once()

    @patch("app.handlers.ai._handle_agent_result", new_callable=AsyncMock)
    @patch("app.handlers.ai.process_message", new_callable=AsyncMock)
    @patch("app.handlers.ai.transcribe_audio", new_callable=AsyncMock)
    @patch("app.handlers.ai.log_user_action", new_callable=AsyncMock)
    @patch("app.handlers.ai.check_ai_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_voice_uses_message_bot_not_import(
        self, mock_rate, mock_log, mock_transcribe, mock_process, mock_handle,
        mock_voice_message, mock_user, mock_session,
    ):
        """Voice handler uses message.bot (not imported bot) for file ops."""
        from app.handlers.ai import handle_voice

        processing_msg = AsyncMock()
        mock_voice_message.answer = AsyncMock(return_value=processing_msg)
        mock_transcribe.return_value = "test"
        mock_process.return_value = AgentState(intent="create_note", note_text="test")

        await handle_voice(mock_voice_message, mock_user, "ru", mock_session)

        # Ensure message.bot was used (not a module-level import)
        mock_voice_message.bot.get_file.assert_called_once()
        mock_voice_message.bot.download_file.assert_called_once()


# =====================================================================
# Integration: full flow with DB (uses session fixture from conftest)
# =====================================================================


class TestAIHandlerIntegrationWithDB:
    """Integration tests using real DB session to verify note/event creation."""

    async def test_create_note_empty_tags_with_db(self, session):
        """Create a note via _handle_agent_result with empty tags — uses real DB."""
        from app.models.user import User
        from app.services.note_service import get_user_notes

        # Create user in DB
        user = User(id=99001, first_name="TestUser", username="test_user")
        session.add(user)
        await session.flush()

        mock_message = AsyncMock()
        mock_processing_msg = AsyncMock()

        state = AgentState(
            intent="create_note",
            note_text="Я хочу книгу От нуля до единицы",
            tag_names=[],  # Empty tags — was causing the bug
            user_language="ru",
        )

        with patch("app.handlers.ai.log_user_action", new_callable=AsyncMock):
            from app.handlers.ai import _handle_agent_result
            await _handle_agent_result(
                mock_message, mock_processing_msg, state, user, "ru", session,
            )

        notes = await get_user_notes(session, user.id)
        assert len(notes) == 1
        assert notes[0].text == "Я хочу книгу От нуля до единицы"
        assert len(notes[0].tags) == 0

    async def test_create_note_with_tags_with_db(self, session):
        """Create a note with tags — uses real DB."""
        from app.models.user import User
        from app.services.note_service import get_user_notes

        user = User(id=99002, first_name="TestUser2", username="test2")
        session.add(user)
        await session.flush()

        mock_message = AsyncMock()
        mock_processing_msg = AsyncMock()

        state = AgentState(
            intent="create_note",
            note_text="Лева хочет в подарок сникерс",
            tag_names=["Лева", "подарки"],
            user_language="ru",
        )

        with patch("app.handlers.ai.log_user_action", new_callable=AsyncMock):
            from app.handlers.ai import _handle_agent_result
            await _handle_agent_result(
                mock_message, mock_processing_msg, state, user, "ru", session,
            )

        notes = await get_user_notes(session, user.id)
        assert len(notes) == 1
        assert notes[0].text == "Лева хочет в подарок сникерс"
        tag_names = sorted([t.name for t in notes[0].tags])
        assert tag_names == ["Лева", "подарки"]

    async def test_create_event_empty_tags_with_db(self, session):
        """Create an event with empty tags — uses real DB."""
        from app.models.user import User
        from app.services.event_service import get_user_events

        user = User(id=99003, first_name="TestUser3", username="test3")
        session.add(user)
        await session.flush()

        mock_message = AsyncMock()
        mock_processing_msg = AsyncMock()

        state = AgentState(
            intent="create_event",
            event_title="Concert",
            event_date=date(2025, 3, 15),
            tag_names=[],
            user_language="en",
        )

        with (
            patch("app.handlers.ai.log_user_action", new_callable=AsyncMock),
            patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock),
        ):
            from app.handlers.ai import _handle_agent_result
            await _handle_agent_result(
                mock_message, mock_processing_msg, state, user, "en", session,
            )

        events = await get_user_events(session, user.id)
        assert len(events) == 1
        assert events[0].title == "Concert"
        assert events[0].event_date == date(2025, 3, 15)

    async def test_create_event_with_tags_with_db(self, session):
        """Create an event with tags — uses real DB."""
        from app.models.user import User
        from app.services.event_service import get_user_events

        user = User(id=99004, first_name="TestUser4", username="test4")
        session.add(user)
        await session.flush()

        mock_message = AsyncMock()
        mock_processing_msg = AsyncMock()

        state = AgentState(
            intent="create_event",
            event_title="Met Leva",
            event_date=date(2026, 2, 6),
            tag_names=["Лева"],
            user_language="ru",
        )

        with (
            patch("app.handlers.ai.log_user_action", new_callable=AsyncMock),
            patch("app.services.beautiful_dates.engine.recalculate_for_event", new_callable=AsyncMock),
        ):
            from app.handlers.ai import _handle_agent_result
            await _handle_agent_result(
                mock_message, mock_processing_msg, state, user, "ru", session,
            )

        events = await get_user_events(session, user.id)
        assert len(events) == 1
        assert events[0].title == "Met Leva"
        tag_names = [t.name for t in events[0].tags]
        assert "Лева" in tag_names
