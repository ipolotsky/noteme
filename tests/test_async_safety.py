"""Tests for async safety — no lazy loading in async context.

Covers:
- Tag view: COUNT queries instead of relationship lazy load
- Graph process_message: dict→AgentState conversion
- Sharing: eager-loaded event access
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import process_message
from app.agents.state import AgentState
from app.models.event import EventTag
from app.models.note import NoteTag
from app.schemas.event import EventCreate
from app.schemas.note import NoteCreate
from app.schemas.user import UserCreate
from app.services.beautiful_date_service import generate_share_uuid, get_by_share_uuid
from app.services.beautiful_dates.engine import recalculate_for_event
from app.services.event_service import create_event
from app.services.note_service import create_note
from app.services.user_service import get_or_create_user


async def _make_user(session: AsyncSession, user_id: int = 123456789):
    data = UserCreate(id=user_id, username="testuser", first_name="Test")
    user, _ = await get_or_create_user(session, data)
    return user


# ---------------------------------------------------------------------------
# Tag view: COUNT queries work in async context
# ---------------------------------------------------------------------------


class TestTagCountQueries:
    """Verify that tag event/note counts work via explicit COUNT queries
    (not relationship lazy load, which fails in async).
    """

    @pytest.mark.asyncio
    async def test_tag_counts_zero_when_no_associations(self, session: AsyncSession, user_id: int):
        await _make_user(session, user_id)
        from app.services.tag_service import create_tag

        tag = await create_tag(session, user_id, "Orphan")

        events_count = (await session.execute(
            select(func.count()).where(EventTag.tag_id == tag.id)
        )).scalar_one()
        notes_count = (await session.execute(
            select(func.count()).where(NoteTag.tag_id == tag.id)
        )).scalar_one()

        assert events_count == 0
        assert notes_count == 0

    @pytest.mark.asyncio
    async def test_tag_counts_with_event(self, session: AsyncSession, user_id: int):
        await _make_user(session, user_id)

        await create_event(
            session, user_id,
            EventCreate(title="Wedding", event_date=date(2022, 8, 17), tag_names=["Max"]),
        )
        # Find the tag
        from app.services.tag_service import get_tag_by_name

        tag = await get_tag_by_name(session, user_id, "Max")
        assert tag is not None

        events_count = (await session.execute(
            select(func.count()).where(EventTag.tag_id == tag.id)
        )).scalar_one()
        assert events_count == 1

    @pytest.mark.asyncio
    async def test_tag_counts_with_note(self, session: AsyncSession, user_id: int):
        await _make_user(session, user_id)

        await create_note(
            session, user_id,
            NoteCreate(text="Buy headphones", tag_names=["Max"]),
        )
        from app.services.tag_service import get_tag_by_name

        tag = await get_tag_by_name(session, user_id, "Max")
        assert tag is not None

        notes_count = (await session.execute(
            select(func.count()).where(NoteTag.tag_id == tag.id)
        )).scalar_one()
        assert notes_count == 1

    @pytest.mark.asyncio
    async def test_tag_counts_with_multiple_associations(self, session: AsyncSession, user_id: int):
        await _make_user(session, user_id)

        await create_event(
            session, user_id,
            EventCreate(title="Wedding", event_date=date(2022, 8, 17), tag_names=["Max"]),
        )
        await create_event(
            session, user_id,
            EventCreate(title="Birthday", event_date=date(2023, 1, 1), tag_names=["Max"]),
        )
        await create_note(
            session, user_id,
            NoteCreate(text="Headphones", tag_names=["Max"]),
        )
        await create_note(
            session, user_id,
            NoteCreate(text="Restaurant", tag_names=["Max"]),
        )
        await create_note(
            session, user_id,
            NoteCreate(text="Book", tag_names=["Max"]),
        )

        from app.services.tag_service import get_tag_by_name

        tag = await get_tag_by_name(session, user_id, "Max")

        events_count = (await session.execute(
            select(func.count()).where(EventTag.tag_id == tag.id)
        )).scalar_one()
        notes_count = (await session.execute(
            select(func.count()).where(NoteTag.tag_id == tag.id)
        )).scalar_one()

        assert events_count == 2
        assert notes_count == 3


# ---------------------------------------------------------------------------
# Graph: process_message converts LangGraph dict result to AgentState
# ---------------------------------------------------------------------------


class TestProcessMessageDictConversion:
    """Verify that process_message converts the dict returned by
    graph.ainvoke() back into an AgentState dataclass.
    """

    @patch("app.agents.graph.get_graph")
    async def test_dict_result_converted_to_agent_state(self, mock_get_graph):
        """graph.ainvoke() returns dict → process_message returns AgentState."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "user_id": 123,
            "user_language": "ru",
            "raw_text": "Свадьба 17.08.2022",
            "is_voice": False,
            "transcribed_text": "Свадьба 17.08.2022",
            "is_valid": True,
            "rejection_reason": "",
            "intent": "create_event",
            "event_title": "Свадьба",
            "event_date": date(2022, 8, 17),
            "event_description": "",
            "tag_names": ["Макс"],
            "note_text": "",
            "note_reminder_date": None,
            "query_type": "",
            "target_entity_id": "",
            "response_text": "Создать событие?",
            "needs_confirmation": True,
            "error": "",
        })
        mock_get_graph.return_value = mock_graph

        result = await process_message("Свадьба 17.08.2022", user_id=123)

        assert isinstance(result, AgentState)
        assert result.intent == "create_event"
        assert result.event_title == "Свадьба"
        assert result.event_date == date(2022, 8, 17)
        assert result.tag_names == ["Макс"]
        assert result.response_text == "Создать событие?"

    @patch("app.agents.graph.get_graph")
    async def test_agent_state_result_preserved(self, mock_get_graph):
        """If graph.ainvoke() already returns AgentState, it's preserved."""
        expected = AgentState(
            user_id=123,
            intent="create_note",
            note_text="Buy milk",
            response_text="Save note?",
        )
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=expected)
        mock_get_graph.return_value = mock_graph

        result = await process_message("Buy milk", user_id=123)

        assert isinstance(result, AgentState)
        assert result.intent == "create_note"
        assert result.note_text == "Buy milk"

    @patch("app.agents.graph.get_graph")
    async def test_handler_can_access_all_fields(self, mock_get_graph):
        """Ensure all fields needed by _handle_agent_result are accessible."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "user_id": 42,
            "user_language": "en",
            "raw_text": "test",
            "is_voice": False,
            "transcribed_text": "test",
            "is_valid": True,
            "rejection_reason": "",
            "intent": "create_event",
            "event_title": "Test Event",
            "event_date": date(2024, 1, 1),
            "event_description": "desc",
            "tag_names": ["tag1", "tag2"],
            "note_text": "",
            "note_reminder_date": None,
            "query_type": "",
            "target_entity_id": "",
            "response_text": "",
            "needs_confirmation": True,
            "error": "",
        })
        mock_get_graph.return_value = mock_graph

        state = await process_message("test", user_id=42, user_language="en")

        # These are the exact fields _handle_agent_result accesses
        assert state.intent == "create_event"
        assert state.event_title == "Test Event"
        assert state.event_date == date(2024, 1, 1)
        assert state.event_description == "desc"
        assert state.tag_names == ["tag1", "tag2"]
        assert state.note_text == ""
        assert state.note_reminder_date is None
        assert state.response_text == ""
        assert state.error == ""


# ---------------------------------------------------------------------------
# Sharing: get_by_share_uuid eagerly loads event
# ---------------------------------------------------------------------------


class TestSharingEagerLoad:
    """Verify get_by_share_uuid loads the event relationship eagerly
    so that bd.event.title and bd.event.user_id are accessible.
    """

    @pytest.mark.asyncio
    async def test_share_uuid_loads_event(self, session: AsyncSession, user_id: int):
        from app.models.beautiful_date_strategy import BeautifulDateStrategy
        from app.utils.seed import STRATEGIES

        await _make_user(session, user_id)

        # Seed strategies directly into the test session
        for data in STRATEGIES:
            session.add(BeautifulDateStrategy(**data))
        await session.flush()

        event = await create_event(
            session, user_id,
            EventCreate(title="Wedding", event_date=date(2022, 8, 17)),
        )
        await recalculate_for_event(session, event)

        # Find a beautiful date for this event
        from app.models.beautiful_date import BeautifulDate

        result = await session.execute(
            select(BeautifulDate).where(BeautifulDate.event_id == event.id).limit(1)
        )
        bd = result.scalar_one_or_none()
        if bd is None:
            pytest.skip("No beautiful dates generated for test event")

        # Generate share UUID
        share_uuid = await generate_share_uuid(session, bd.id)
        assert share_uuid is not None

        # Fetch via share UUID (this is the function used in sharing.py)
        loaded = await get_by_share_uuid(session, share_uuid)
        assert loaded is not None

        # These should NOT trigger lazy load — event is eagerly loaded
        assert loaded.event is not None
        assert loaded.event.title == "Wedding"
        assert loaded.event.user_id == user_id
