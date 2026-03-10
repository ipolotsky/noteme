"""Edge case tests from spec section 16."""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.wish import WishCreate
from app.services.event_service import (
    EventLimitError,
    create_event,
    delete_event,
    get_event,
    get_user_events,
)
from app.services.person_service import create_person, delete_person, get_or_create_people
from app.services.wish_service import (
    WishLimitError,
    create_wish,
)
from app.utils.date_utils import format_date, format_relative_date, parse_date


@pytest.fixture
async def user(session: AsyncSession) -> User:
    """Create a test user with standard limits."""
    u = User(id=111222333, first_name="Test", language="ru", max_events=10, max_wishes=10)
    session.add(u)
    await session.flush()
    return u


class TestEventEdgeCases:
    async def test_future_date_allowed(self, session, user):
        """Events with future dates should be accepted."""
        future = date.today() + timedelta(days=365)
        event = await create_event(
            session, user.id, EventCreate(title="Future", event_date=future)
        )
        assert event.event_date == future

    async def test_very_old_event_allowed(self, session, user):
        """Events more than 100 years ago should be allowed."""
        old_date = date(1920, 1, 1)
        event = await create_event(
            session, user.id, EventCreate(title="Ancient", event_date=old_date)
        )
        assert event.event_date == old_date

    async def test_two_events_same_name(self, session, user):
        """Two events with the same name but different UUIDs are allowed."""
        e1 = await create_event(
            session, user.id, EventCreate(title="Birthday", event_date=date(2000, 1, 1))
        )
        e2 = await create_event(
            session, user.id, EventCreate(title="Birthday", event_date=date(2005, 6, 15))
        )
        assert e1.id != e2.id
        assert e1.title == e2.title

    async def test_system_event_cannot_be_deleted(self, session, user):
        """System events are protected from deletion."""
        event = await create_event(
            session,
            user.id,
            EventCreate(title="Registration", event_date=date.today(), is_system=True),
        )
        result = await delete_event(session, event.id)
        assert result is False
        # Event still exists
        assert await get_event(session, event.id) is not None

    async def test_exceeding_max_events_limit(self, session):
        """Exceeding max_events raises EventLimitError."""
        u = User(id=999888777, first_name="Limit", max_events=2)
        session.add(u)
        await session.flush()

        await create_event(session, u.id, EventCreate(title="E1", event_date=date.today()))
        await create_event(session, u.id, EventCreate(title="E2", event_date=date.today()))

        with pytest.raises(EventLimitError):
            await create_event(session, u.id, EventCreate(title="E3", event_date=date.today()))

    async def test_delete_last_event_leaves_empty(self, session, user):
        """Deleting the last event leaves the user with no events."""
        event = await create_event(
            session, user.id, EventCreate(title="Solo", event_date=date.today())
        )
        await delete_event(session, event.id)
        events = await get_user_events(session, user.id)
        assert len(events) == 0

    async def test_event_with_empty_description(self, session, user):
        """Events without description should work."""
        event = await create_event(
            session,
            user.id,
            EventCreate(title="No Desc", event_date=date.today(), description=None),
        )
        assert event.description is None

    async def test_event_with_many_tags(self, session, user):
        """Events can have multiple tags."""
        event = await create_event(
            session,
            user.id,
            EventCreate(
                title="Multi-tag",
                event_date=date.today(),
                person_names=["Love", "Family", "Important"],
            ),
        )
        assert len(event.people) == 3


class TestWishEdgeCases:
    async def test_wish_limit_enforcement(self, session):
        """Exceeding max_wishes raises WishLimitError."""
        u = User(id=999888776, first_name="WishLim", max_wishes=1)
        session.add(u)
        await session.flush()

        await create_wish(session, u.id, WishCreate(text="Wish 1"))
        with pytest.raises(WishLimitError):
            await create_wish(session, u.id, WishCreate(text="Wish 2"))

    async def test_wish_without_people(self, session, user):
        """Wishes without people work fine."""
        wish = await create_wish(session, user.id, WishCreate(text="Plain wish"))
        assert wish.people == []


class TestPersonEdgeCases:
    async def test_case_insensitive_person_dedup(self, session, user):
        """People with same name different case are deduplicated."""
        people = await get_or_create_people(session, user.id, ["Max", "max", "MAX"])
        assert len(people) == 1
        assert people[0].name == "Max"

    async def test_person_deletion(self, session, user):
        """Deleting a person works."""
        person = await create_person(session, user.id, "ToDelete")
        result = await delete_person(session, person.id)
        assert result is True

    async def test_empty_person_names_filtered(self, session, user):
        """Empty strings in person list are filtered out."""
        people = await get_or_create_people(session, user.id, ["", "  ", "Valid"])
        assert len(people) == 1
        assert people[0].name == "Valid"


class TestDateUtilsEdgeCases:
    def test_parse_date_dd_mm_yyyy(self):
        result = parse_date("17.08.2022")
        assert result == date(2022, 8, 17)

    def test_parse_date_slash_format(self):
        result = parse_date("17/08/2022")
        assert result == date(2022, 8, 17)

    def test_parse_date_iso_format(self):
        result = parse_date("2022-08-17")
        assert result == date(2022, 8, 17)

    def test_parse_invalid_date(self):
        result = parse_date("30.02.2022")
        assert result is None

    def test_parse_garbage(self):
        result = parse_date("not a date")
        assert result is None

    def test_parse_date_with_whitespace(self):
        result = parse_date("  17.08.2022  ")
        assert result == date(2022, 8, 17)

    def test_format_relative_today(self):
        result = format_relative_date(date.today(), "ru")
        # Should return "today" in Russian
        assert result  # Non-empty

    def test_format_relative_tomorrow(self):
        tomorrow = date.today() + timedelta(days=1)
        result = format_relative_date(tomorrow, "ru")
        assert result  # Non-empty

    def test_format_relative_in_week(self):
        in_week = date.today() + timedelta(days=7)
        result = format_relative_date(in_week, "ru")
        assert result

    def test_format_relative_past(self):
        past = date.today() - timedelta(days=10)
        result = format_relative_date(past, "ru")
        assert result  # Returns formatted date

    def test_format_date_russian(self):
        result = format_date(date(2022, 8, 17), "ru")
        assert "17" in result
        assert "августа" in result
        assert "2022" in result

    def test_format_date_english(self):
        result = format_date(date(2022, 8, 17), "en")
        assert "17" in result
        assert "2022" in result
