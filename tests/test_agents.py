"""Agent integration tests with mocked OpenAI LLM calls."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.event_agent import event_agent_node
from app.agents.formatter_agent import formatter_node
from app.agents.query_agent import query_agent_node
from app.agents.router_agent import VALID_INTENTS, router_node
from app.agents.state import AgentState
from app.agents.validation_agent import validation_node
from app.agents.whisper import whisper_node
from app.agents.wish_agent import wish_agent_node

# --- Whisper node ---


class TestWhisperNode:
    async def test_text_message_passthrough(self):
        state = AgentState(raw_text="Hello world", is_voice=False)
        result = await whisper_node(state)
        assert result.transcribed_text == "Hello world"

    async def test_voice_passthrough_when_text_already_set(self):
        state = AgentState(raw_text="some text", is_voice=True)
        result = await whisper_node(state)
        assert result.transcribed_text == "some text"

    async def test_empty_text(self):
        state = AgentState(raw_text="", is_voice=False)
        result = await whisper_node(state)
        assert result.transcribed_text == ""


# --- Validation node ---


class TestValidationNode:
    async def test_empty_message_invalid(self):
        state = AgentState(raw_text="")
        result = await validation_node(state)
        assert not result.is_valid
        assert result.rejection_reason == "Empty message"

    @patch("app.agents.validation_agent.ChatOpenAI")
    async def test_valid_message(self, mock_llm_cls):
        mock_response = AsyncMock()
        mock_response.content = "valid"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="Запомни дату свадьбы 17.08.2022")
        result = await validation_node(state)
        assert result.is_valid

    @patch("app.agents.validation_agent.ChatOpenAI")
    async def test_invalid_off_topic(self, mock_llm_cls):
        mock_response = AsyncMock()
        mock_response.content = "invalid\nThis is off-topic"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="сколько будет 2+2")
        result = await validation_node(state)
        assert not result.is_valid
        assert result.rejection_reason == "this is off-topic"  # lowercased by validation_node


# --- Router node ---


class TestRouterNode:
    @pytest.mark.parametrize("intent", list(VALID_INTENTS))
    @patch("app.agents.router_agent.ChatOpenAI")
    async def test_valid_intents(self, mock_llm_cls, intent):
        mock_response = AsyncMock()
        mock_response.content = intent
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="test message")
        result = await router_node(state)
        assert result.intent == intent

    @patch("app.agents.router_agent.ChatOpenAI")
    async def test_unknown_intent_defaults_to_create_wish(self, mock_llm_cls):
        mock_response = AsyncMock()
        mock_response.content = "completely_unknown_intent"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="test message")
        result = await router_node(state)
        assert result.intent == "create_wish"


# --- Event agent node ---


class TestEventAgentNode:
    @patch("app.agents.event_agent.ChatOpenAI")
    async def test_extract_event(self, mock_llm_cls):
        mock_response = AsyncMock()
        mock_response.content = '{"title": "Свадьба", "date": "2022-08-17", "description": "", "people": ["Макс"]}'
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="Свадьба с Максом 17.08.2022")
        result = await event_agent_node(state)
        assert result.event_title == "Свадьба"
        assert result.event_date == date(2022, 8, 17)
        assert result.person_names == ["Макс"]
        assert result.needs_confirmation

    @patch("app.agents.event_agent.ChatOpenAI")
    async def test_extract_event_markdown_wrapped(self, mock_llm_cls):
        mock_response = AsyncMock()
        mock_response.content = '```json\n{"title": "Birthday", "date": "2000-01-15", "description": "", "people": []}\n```'
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="Birthday 15 Jan 2000")
        result = await event_agent_node(state)
        assert result.event_title == "Birthday"
        assert result.event_date == date(2000, 1, 15)

    @patch("app.agents.event_agent.ChatOpenAI")
    async def test_parse_error(self, mock_llm_cls):
        mock_response = AsyncMock()
        mock_response.content = "I don't understand"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="garbled text")
        result = await event_agent_node(state)
        assert result.error == "parse_error"


# --- Wish agent node ---


class TestWishAgentNode:
    @patch("app.agents.wish_agent.ChatOpenAI")
    async def test_extract_wish(self, mock_llm_cls):
        mock_response = AsyncMock()
        mock_response.content = '{"text": "Хочет наушники Sony", "people": ["Макс"]}'
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="Макс хочет наушники Sony")
        result = await wish_agent_node(state)
        assert result.wish_text == "Хочет наушники Sony"
        assert result.person_names == ["Макс"]
        assert result.needs_confirmation

    @patch("app.agents.wish_agent.ChatOpenAI")
    async def test_fallback_uses_raw_text(self, mock_llm_cls):
        mock_response = AsyncMock()
        mock_response.content = "not valid json at all"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm

        state = AgentState(raw_text="купить молоко")
        result = await wish_agent_node(state)
        assert result.wish_text == "купить молоко"
        assert result.needs_confirmation


# --- Query agent node ---


class TestQueryAgentNode:
    async def test_keyword_events(self):
        state = AgentState(raw_text="покажи мои события")
        result = await query_agent_node(state)
        assert result.query_type == "events"

    async def test_keyword_wishes(self):
        state = AgentState(raw_text="покажи мои желания")
        result = await query_agent_node(state)
        assert result.query_type == "wishes"

    async def test_keyword_feed(self):
        state = AgentState(raw_text="открой ленту красивых дат")
        result = await query_agent_node(state)
        assert result.query_type == "feed"

    async def test_keyword_people(self):
        state = AgentState(raw_text="покажи людей")
        result = await query_agent_node(state)
        assert result.query_type == "people"

    async def test_keyword_events_english(self):
        state = AgentState(raw_text="show my events")
        result = await query_agent_node(state)
        assert result.query_type == "events"

    async def test_keyword_wishes_english(self):
        state = AgentState(raw_text="my wishes")
        result = await query_agent_node(state)
        assert result.query_type == "wishes"


# --- Formatter node ---


class TestFormatterNode:
    async def test_format_error(self):
        state = AgentState(error="parse_error", user_language="ru")
        result = await formatter_node(state)
        assert result.response_text  # Should have error message

    async def test_format_invalid(self):
        state = AgentState(is_valid=False, user_language="ru")
        result = await formatter_node(state)
        assert result.response_text  # Should have off-topic message

    async def test_format_create_event_with_data(self):
        state = AgentState(
            intent="create_event",
            event_title="Свадьба",
            event_date=date(2022, 8, 17),
            user_language="ru",
        )
        result = await formatter_node(state)
        assert result.response_text
        assert result.needs_confirmation

    async def test_format_create_event_missing_date(self):
        state = AgentState(
            intent="create_event",
            event_title="Свадьба",
            user_language="ru",
        )
        result = await formatter_node(state)
        assert result.response_text  # Should ask for date

    async def test_format_create_wish_with_text(self):
        state = AgentState(
            intent="create_wish",
            wish_text="Купить наушники",
            user_language="ru",
        )
        result = await formatter_node(state)
        assert result.response_text
        assert result.needs_confirmation

    async def test_format_view_intents(self):
        for intent in ("view_events", "view_wishes", "view_feed", "view_people"):
            state = AgentState(intent=intent, user_language="ru")
            result = await formatter_node(state)
            assert result.response_text == ""  # Handler shows list

    async def test_format_help(self):
        state = AgentState(intent="help", user_language="ru")
        result = await formatter_node(state)
        assert result.response_text
