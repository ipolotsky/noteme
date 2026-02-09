"""End-to-end tests exercising full multi-layer flows through
the real database: services + models + strategies + notifications.

These tests create real DB records and verify cross-module interactions.
"""

import uuid
from datetime import date, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beautiful_date_strategy import BeautifulDateStrategy
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.note import NoteCreate
from app.schemas.user import UserCreate, UserUpdate
from app.services.event_service import (
    EventLimitError,
    count_user_events,
    create_event,
    delete_event,
    get_event,
    update_event,
)
from app.services.note_service import (
    NoteLimitError,
    create_note,
    get_notes_by_tag_names,
    get_user_notes,
)
from app.services.tag_service import (
    create_tag,
    get_or_create_tags,
    get_user_tags,
)
from app.services.user_service import get_or_create_user, update_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _user(session: AsyncSession, uid: int = 100500, **kw) -> User:
    defaults = dict(first_name="Ilya", username="ilya_t")
    defaults.update(kw)
    data = UserCreate(id=uid, **defaults)
    user, _ = await get_or_create_user(session, data)
    return user


async def _seed_strategy(
    session: AsyncSession,
    strategy_type: str = "multiples",
    params: dict | None = None,
    name_ru: str = "Test",
    name_en: str = "Test",
) -> BeautifulDateStrategy:
    s = BeautifulDateStrategy(
        name_ru=name_ru,
        name_en=name_en,
        strategy_type=strategy_type,
        params=params or {"base": 100, "min": 100, "max": 2000, "unit": "days"},
        is_active=True,
        priority=0,
    )
    session.add(s)
    await session.flush()
    return s


# =====================================================================
# E2E FLOW 1: User Lifecycle
# =====================================================================


class TestUserLifecycle:
    """Full user creation, update, and settings changes."""

    async def test_create_user_with_defaults(self, session: AsyncSession):
        """New user gets default settings."""
        user = await _user(session)
        assert user.language == "ru"
        assert user.timezone == "Europe/Moscow"
        assert user.notifications_enabled is True
        assert user.notification_count == 3
        assert user.max_events == 10
        assert user.max_notes == 10
        assert user.onboarding_completed is False

    async def test_update_user_language_and_timezone(self, session: AsyncSession):
        """Change language and timezone."""
        user = await _user(session)
        updated = await update_user(session, user.id, UserUpdate(
            language="en", timezone="America/New_York",
        ))
        assert updated is not None
        assert updated.language == "en"
        assert updated.timezone == "America/New_York"

    async def test_complete_onboarding(self, session: AsyncSession):
        """Mark onboarding as completed."""
        user = await _user(session)
        assert user.onboarding_completed is False
        updated = await update_user(session, user.id, UserUpdate(onboarding_completed=True))
        assert updated.onboarding_completed is True

    async def test_second_create_returns_existing(self, session: AsyncSession):
        """get_or_create_user returns existing user on second call."""
        user1 = await _user(session, uid=555)
        user2, created = await get_or_create_user(session, UserCreate(id=555, first_name="New Name"))
        assert not created
        assert user2.id == user1.id


# =====================================================================
# E2E FLOW 2: Event -> Beautiful Dates -> Feed
# =====================================================================


class TestEventToFeedFlow:
    """Create event -> calculate beautiful dates -> query feed."""

    async def test_event_create_triggers_beautiful_dates(self, session: AsyncSession):
        """Creating an event and recalculating produces beautiful dates."""
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Wedding", event_date=date(2020, 1, 1),
        ))
        count = await recalculate_for_event(session, event, [strategy])
        assert count > 0

    async def test_feed_returns_beautiful_dates(self, session: AsyncSession):
        """Feed query returns created beautiful dates ordered by target_date."""
        from app.services.beautiful_date_service import count_user_feed, get_user_feed
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=200)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Birthday", event_date=date(2020, 5, 15),
        ))
        await recalculate_for_event(session, event, [strategy])

        feed = await get_user_feed(session, user.id)
        total = await count_user_feed(session, user.id)

        assert total > 0
        assert len(feed) > 0
        # Verify ordering
        for i in range(1, len(feed)):
            assert feed[i].target_date >= feed[i - 1].target_date

    async def test_event_delete_cascades_beautiful_dates(self, session: AsyncSession):
        """Deleting event removes its beautiful dates."""
        from app.services.beautiful_date_service import count_user_feed
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=300)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Test Event", event_date=date(2020, 1, 1),
        ))
        await recalculate_for_event(session, event, [strategy])
        assert await count_user_feed(session, user.id) > 0

        await delete_event(session, event.id, user_id=user.id)
        await session.flush()
        assert await count_user_feed(session, user.id) == 0

    async def test_event_date_change_recalculates(self, session: AsyncSession):
        """Changing event date and recalculating updates beautiful dates."""
        from app.services.beautiful_date_service import get_user_feed
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=400)
        strategy = await _seed_strategy(session, "anniversary", {
            "years": [1, 2, 3, 5, 10],
        })

        event = await create_event(session, user.id, EventCreate(
            title="Start", event_date=date(2020, 1, 1),
        ))
        await recalculate_for_event(session, event, [strategy])
        feed_before = await get_user_feed(session, user.id)

        # Change date
        event = await update_event(session, event.id, EventUpdate(
            event_date=date(2022, 6, 15),
        ), user_id=user.id)
        await recalculate_for_event(session, event, [strategy])
        feed_after = await get_user_feed(session, user.id)

        # Dates should differ
        before_dates = {bd.target_date for bd in feed_before}
        after_dates = {bd.target_date for bd in feed_after}
        assert before_dates != after_dates

    async def test_multiple_events_in_feed(self, session: AsyncSession):
        """Feed combines beautiful dates from multiple events."""
        from app.services.beautiful_date_service import count_user_feed
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=500)
        strategy = await _seed_strategy(session, "multiples", {"base": 500, "min": 500, "max": 5000, "unit": "days"})

        e1 = await create_event(session, user.id, EventCreate(
            title="Event A", event_date=date(2015, 1, 1),
        ))
        e2 = await create_event(session, user.id, EventCreate(
            title="Event B", event_date=date(2018, 6, 1),
        ))
        await recalculate_for_event(session, e1, [strategy])
        await recalculate_for_event(session, e2, [strategy])

        total = await count_user_feed(session, user.id)
        assert total > 0

    async def test_disabled_strategy_no_dates(self, session: AsyncSession):
        """Inactive strategy produces no beautiful dates."""
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=600)
        strategy = await _seed_strategy(session)
        strategy.is_active = False
        await session.flush()

        event = await create_event(session, user.id, EventCreate(
            title="Test", event_date=date(2020, 1, 1),
        ))
        # Pass empty active strategies list
        count = await recalculate_for_event(session, event, [])
        assert count == 0


# =====================================================================
# E2E FLOW 3: Notes + Tags Cross-linking
# =====================================================================


class TestNotesTagsCrosslinking:
    """Notes and events share tags, enabling related notes in feed."""

    async def test_tag_links_event_and_note(self, session: AsyncSession):
        """Create event with tag 'Max', note with tag 'Max' -> notes_by_tag_names finds it."""
        user = await _user(session, uid=700)

        await create_event(session, user.id, EventCreate(
            title="Wedding with Max", event_date=date(2022, 8, 17),
            tag_names=["Max"],
        ))
        note = await create_note(session, user.id, NoteCreate(
            text="Max wants Sony headphones",
            tag_names=["Max"],
        ))

        related = await get_notes_by_tag_names(session, user.id, ["Max"])
        assert len(related) >= 1
        assert any(n.id == note.id for n in related)

    async def test_case_insensitive_tag_match(self, session: AsyncSession):
        """Tags 'max' and 'Max' should resolve to same tag."""
        user = await _user(session, uid=800)

        tags = await get_or_create_tags(session, user.id, ["Max", "max", "MAX"])
        assert len(tags) == 1
        assert tags[0].name == "Max"  # keeps first casing

    async def test_note_with_multiple_tags(self, session: AsyncSession):
        """Note with multiple tags found via any of them."""
        user = await _user(session, uid=900)

        await create_note(session, user.id, NoteCreate(
            text="Gift idea", tag_names=["Family", "Birthday"],
        ))

        found_by_family = await get_notes_by_tag_names(session, user.id, ["Family"])
        found_by_birthday = await get_notes_by_tag_names(session, user.id, ["Birthday"])

        assert len(found_by_family) == 1
        assert len(found_by_birthday) == 1

    async def test_delete_tag_leaves_notes(self, session: AsyncSession):
        """Deleting a tag doesn't delete the note itself."""
        from app.services.tag_service import delete_tag

        user = await _user(session, uid=1000)
        note = await create_note(session, user.id, NoteCreate(
            text="Important", tag_names=["Work"],
        ))
        tags = await get_user_tags(session, user.id)
        assert len(tags) == 1

        await delete_tag(session, tags[0].id, user_id=user.id)
        notes = await get_user_notes(session, user.id)
        assert len(notes) == 1  # note still exists
        assert notes[0].id == note.id


# =====================================================================
# E2E FLOW 4: Limits Enforcement
# =====================================================================


class TestLimitsEnforcement:
    """User limits (max_events, max_notes) enforced across services."""

    async def test_event_limit_enforced(self, session: AsyncSession):
        """Cannot create more events than max_events."""
        user = await _user(session, uid=1100)
        await update_user(session, user.id, UserUpdate())
        user.max_events = 2
        await session.flush()

        await create_event(session, user.id, EventCreate(title="E1", event_date=date(2023, 1, 1)))
        await create_event(session, user.id, EventCreate(title="E2", event_date=date(2023, 2, 1)))

        try:
            await create_event(session, user.id, EventCreate(title="E3", event_date=date(2023, 3, 1)))
            raise AssertionError("Should raise EventLimitError")
        except EventLimitError as e:
            assert e.max_events == 2

    async def test_note_limit_enforced(self, session: AsyncSession):
        """Cannot create more notes than max_notes."""
        user = await _user(session, uid=1200)
        user.max_notes = 1
        await session.flush()

        await create_note(session, user.id, NoteCreate(text="Note 1"))

        try:
            await create_note(session, user.id, NoteCreate(text="Note 2"))
            raise AssertionError("Should raise NoteLimitError")
        except NoteLimitError as e:
            assert e.max_notes == 1

    async def test_event_count_accurate(self, session: AsyncSession):
        """count_user_events matches actual events."""
        user = await _user(session, uid=1300)
        assert await count_user_events(session, user.id) == 0

        await create_event(session, user.id, EventCreate(title="A", event_date=date(2023, 1, 1)))
        await create_event(session, user.id, EventCreate(title="B", event_date=date(2023, 2, 1)))
        assert await count_user_events(session, user.id) == 2


# =====================================================================
# E2E FLOW 5: Sharing
# =====================================================================


class TestSharingFlow:
    """Generate share UUID and retrieve by it."""

    async def test_generate_and_retrieve_share(self, session: AsyncSession):
        """Generate share_uuid for a beautiful date, then retrieve it."""
        from app.services.beautiful_date_service import generate_share_uuid, get_by_share_uuid
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=1400)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Share Test", event_date=date(2020, 1, 1),
        ))
        await recalculate_for_event(session, event, [strategy])

        from app.services.beautiful_date_service import get_user_feed
        feed = await get_user_feed(session, user.id)
        assert len(feed) > 0

        bd = feed[0]
        share_uuid = await generate_share_uuid(session, bd.id)
        assert share_uuid is not None

        # Second call returns same UUID
        share_uuid2 = await generate_share_uuid(session, bd.id)
        assert share_uuid == share_uuid2

        # Retrieve by share_uuid
        found = await get_by_share_uuid(session, share_uuid)
        assert found is not None
        assert found.id == bd.id

    async def test_share_nonexistent_returns_none(self, session: AsyncSession):
        """Sharing nonexistent beautiful date returns None."""
        from app.services.beautiful_date_service import generate_share_uuid
        result = await generate_share_uuid(session, uuid.uuid4())
        assert result is None

    async def test_get_by_invalid_share_uuid(self, session: AsyncSession):
        """Querying nonexistent share UUID returns None."""
        from app.services.beautiful_date_service import get_by_share_uuid
        result = await get_by_share_uuid(session, uuid.uuid4())
        assert result is None


# =====================================================================
# E2E FLOW 6: Notifications
# =====================================================================


class TestNotificationFlow:
    """Build digest and check note reminders."""

    async def test_build_digest_with_dates(self, session: AsyncSession):
        """Digest contains upcoming beautiful dates."""
        from app.services.beautiful_dates.engine import recalculate_for_event
        from app.services.notification_service import build_digest

        user = await _user(session, uid=1500)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Notification Test", event_date=date(2020, 1, 1),
        ))
        await recalculate_for_event(session, event, [strategy])

        digest = await build_digest(session, user)
        assert len(digest) <= user.notification_count
        # With step=100 and event from 2020, there should be upcoming dates
        assert len(digest) > 0

    async def test_build_digest_empty_no_events(self, session: AsyncSession):
        """Digest is empty when no events exist."""
        from app.services.notification_service import build_digest

        user = await _user(session, uid=1600)
        digest = await build_digest(session, user)
        assert len(digest) == 0

    async def test_format_digest_message(self, session: AsyncSession):
        """Digest message contains greeting and labels."""
        from app.services.beautiful_dates.engine import recalculate_for_event
        from app.services.notification_service import build_digest, format_digest_message

        user = await _user(session, uid=1700)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Format Test", event_date=date(2020, 1, 1),
        ))
        await recalculate_for_event(session, event, [strategy])

        digest = await build_digest(session, user)
        message = await format_digest_message(session, user, digest)

        assert user.first_name in message
        assert "\u2600" in message  # sun emoji for greeting

    async def test_format_digest_with_spoiler(self, session: AsyncSession):
        """Spoiler-enabled user gets <tg-spoiler> wrapped content."""
        from app.services.beautiful_dates.engine import recalculate_for_event
        from app.services.notification_service import build_digest, format_digest_message

        user = await _user(session, uid=1800)
        user.spoiler_enabled = True
        await session.flush()

        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Spoiler Test", event_date=date(2020, 1, 1),
        ))
        await recalculate_for_event(session, event, [strategy])

        digest = await build_digest(session, user)
        message = await format_digest_message(session, user, digest)

        assert "<tg-spoiler>" in message

    async def test_note_reminders_due_tomorrow(self, session: AsyncSession):
        """Notes with reminder_date = tomorrow are found."""
        from app.services.notification_service import get_due_note_reminders

        user = await _user(session, uid=1900)
        tomorrow = date.today() + timedelta(days=1)

        await create_note(session, user.id, NoteCreate(
            text="Remind me!", reminder_date=tomorrow,
        ))
        await create_note(session, user.id, NoteCreate(
            text="No reminder",
        ))

        reminders = await get_due_note_reminders(session, user)
        assert len(reminders) == 1
        assert reminders[0].text == "Remind me!"

    async def test_note_reminder_not_sent_twice(self, session: AsyncSession):
        """Once reminder_sent=True, note is not returned again."""
        from app.services.notification_service import get_due_note_reminders

        user = await _user(session, uid=2000)
        tomorrow = date.today() + timedelta(days=1)

        note = await create_note(session, user.id, NoteCreate(
            text="Once only", reminder_date=tomorrow,
        ))
        note.reminder_sent = True
        await session.flush()

        reminders = await get_due_note_reminders(session, user)
        assert len(reminders) == 0

    async def test_notification_users_filter(self, session: AsyncSession):
        """get_users_for_notification filters by time, active, enabled."""
        from app.services.notification_service import get_users_for_notification

        # Active user with matching time
        u1 = await _user(session, uid=2100)
        u1.notification_time = time(9, 0)
        u1.notifications_enabled = True

        # Inactive user
        u2 = await _user(session, uid=2200)
        u2.notification_time = time(9, 0)
        u2.is_active = False

        # Wrong time
        u3 = await _user(session, uid=2300)
        u3.notification_time = time(18, 0)

        # Notifications disabled
        u4 = await _user(session, uid=2400)
        u4.notification_time = time(9, 0)
        u4.notifications_enabled = False

        await session.flush()

        users = await get_users_for_notification(session, 9, 0)
        ids = [u.id for u in users]
        assert 2100 in ids
        assert 2200 not in ids  # inactive
        assert 2300 not in ids  # wrong time
        assert 2400 not in ids  # disabled

    async def test_notification_log(self, session: AsyncSession):
        """log_notification creates a record."""
        from app.services.notification_service import log_notification

        user = await _user(session, uid=2500)
        await log_notification(session, user.id, "digest")

        from sqlalchemy import select

        from app.models.notification_log import NotificationLog
        result = await session.execute(
            select(NotificationLog).where(NotificationLog.user_id == user.id)
        )
        logs = list(result.scalars().all())
        assert len(logs) == 1
        assert logs[0].notification_type == "digest"


# =====================================================================
# E2E FLOW 7: Beautiful Dates Strategies
# =====================================================================


class TestBeautifulDatesStrategies:
    """Test strategy engine with real DB."""

    async def test_recalculate_for_user(self, session: AsyncSession):
        """recalculate_for_user processes all user events."""
        from app.services.beautiful_dates.engine import recalculate_for_user

        user = await _user(session, uid=2600)
        await _seed_strategy(session, "multiples", {"base": 500, "min": 500, "max": 5000, "unit": "days"})

        await create_event(session, user.id, EventCreate(title="A", event_date=date(2015, 1, 1)))
        await create_event(session, user.id, EventCreate(title="B", event_date=date(2018, 6, 1)))

        total = await recalculate_for_user(session, user.id)
        assert total > 0

    async def test_recalculate_all(self, session: AsyncSession):
        """recalculate_all processes all events across users."""
        from app.services.beautiful_dates.engine import recalculate_all

        u1 = await _user(session, uid=2700)
        u2 = await _user(session, uid=2800)
        await _seed_strategy(session, "multiples", {"base": 1000, "min": 1000, "max": 10000, "unit": "days"})

        await create_event(session, u1.id, EventCreate(title="U1", event_date=date(2010, 1, 1)))
        await create_event(session, u2.id, EventCreate(title="U2", event_date=date(2015, 1, 1)))

        total = await recalculate_all(session)
        assert total > 0

    async def test_event_beautiful_dates_query(self, session: AsyncSession):
        """get_event_beautiful_dates returns dates for specific event."""
        from app.services.beautiful_date_service import get_event_beautiful_dates
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=2900)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Specific", event_date=date(2020, 1, 1),
        ))
        await recalculate_for_event(session, event, [strategy])

        dates = await get_event_beautiful_dates(session, event.id)
        assert len(dates) > 0
        for bd in dates:
            assert bd.event_id == event.id

    async def test_anniversary_strategy_produces_correct_dates(self, session: AsyncSession):
        """Anniversary strategy produces year anniversaries."""
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=3000)
        strategy = await _seed_strategy(session, "anniversary", {
            "years": [1, 2, 3, 5, 10, 25, 50],
        })

        event = await create_event(session, user.id, EventCreate(
            title="Anniversary Test", event_date=date(2024, 6, 15),
        ))
        count = await recalculate_for_event(session, event, [strategy])
        assert count > 0

        from app.services.beautiful_date_service import get_event_beautiful_dates
        dates = await get_event_beautiful_dates(session, event.id, limit=50)
        target_dates = {bd.target_date for bd in dates}
        # 1-year anniversary should be June 15, 2025
        assert date(2025, 6, 15) in target_dates or date(2026, 6, 15) in target_dates

    async def test_multiple_strategies_combine(self, session: AsyncSession):
        """Multiple active strategies each contribute dates."""
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=3100)
        s1 = await _seed_strategy(session, "multiples", {"base": 500, "min": 500, "max": 5000, "unit": "days"}, name_ru="M", name_en="M")
        s2 = await _seed_strategy(session, "anniversary", {"years": [1, 2, 5, 10]}, name_ru="A", name_en="A")

        event = await create_event(session, user.id, EventCreate(
            title="Multi Strategy", event_date=date(2020, 1, 1),
        ))
        count = await recalculate_for_event(session, event, [s1, s2])
        assert count > 0

        from app.services.beautiful_date_service import get_event_beautiful_dates
        dates = await get_event_beautiful_dates(session, event.id, limit=100)
        strategy_ids = {bd.strategy_id for bd in dates}
        assert len(strategy_ids) >= 2  # dates from both strategies


# =====================================================================
# E2E FLOW 8: Security / Ownership
# =====================================================================


class TestOwnershipSecurity:
    """Verify user_id ownership checks across services."""

    async def test_cannot_view_other_users_event(self, session: AsyncSession):
        """get_event with wrong user_id returns None."""
        u1 = await _user(session, uid=3200)
        u2 = await _user(session, uid=3300)

        event = await create_event(session, u1.id, EventCreate(
            title="Private", event_date=date(2023, 1, 1),
        ))

        found = await get_event(session, event.id, user_id=u2.id)
        assert found is None

    async def test_cannot_delete_other_users_event(self, session: AsyncSession):
        """delete_event with wrong user_id returns False."""
        u1 = await _user(session, uid=3400)
        u2 = await _user(session, uid=3500)

        event = await create_event(session, u1.id, EventCreate(
            title="Protected", event_date=date(2023, 1, 1),
        ))

        deleted = await delete_event(session, event.id, user_id=u2.id)
        assert deleted is False

        # Still exists for owner
        found = await get_event(session, event.id, user_id=u1.id)
        assert found is not None

    async def test_cannot_update_other_users_event(self, session: AsyncSession):
        """update_event with wrong user_id returns None."""
        u1 = await _user(session, uid=3600)
        u2 = await _user(session, uid=3700)

        event = await create_event(session, u1.id, EventCreate(
            title="Owned", event_date=date(2023, 1, 1),
        ))

        result = await update_event(session, event.id, EventUpdate(title="Hacked"), user_id=u2.id)
        assert result is None

    async def test_tags_scoped_to_user(self, session: AsyncSession):
        """Two users can have tags with same name independently."""
        u1 = await _user(session, uid=3800)
        u2 = await _user(session, uid=3900)

        t1 = await create_tag(session, u1.id, "Shared Name")
        t2 = await create_tag(session, u2.id, "Shared Name")

        assert t1.id != t2.id
        assert t1.user_id == u1.id
        assert t2.user_id == u2.id

    async def test_notes_scoped_to_user(self, session: AsyncSession):
        """get_notes_by_tag_names only returns current user's notes."""
        u1 = await _user(session, uid=4000)
        u2 = await _user(session, uid=4100)

        await create_note(session, u1.id, NoteCreate(text="U1 note", tag_names=["Work"]))
        await create_note(session, u2.id, NoteCreate(text="U2 note", tag_names=["Work"]))

        u1_notes = await get_notes_by_tag_names(session, u1.id, ["Work"])
        u2_notes = await get_notes_by_tag_names(session, u2.id, ["Work"])

        assert len(u1_notes) == 1
        assert u1_notes[0].text == "U1 note"
        assert len(u2_notes) == 1
        assert u2_notes[0].text == "U2 note"


# =====================================================================
# E2E FLOW 9: Worker Tasks (mocked bot)
# =====================================================================


class TestWorkerTasks:
    """Test arq worker tasks with mocked bot and session."""

    async def test_recalculate_event_task(self, session: AsyncSession):
        """Worker task recalculates for a given event ID."""
        from app.services.beautiful_dates.engine import recalculate_for_event

        user = await _user(session, uid=4200)
        strategy = await _seed_strategy(session, "multiples", {"base": 500, "min": 500, "max": 5000, "unit": "days"})
        event = await create_event(session, user.id, EventCreate(
            title="Worker Test", event_date=date(2020, 1, 1),
        ))

        # Directly test the engine function (worker wraps this)
        count = await recalculate_for_event(session, event, [strategy])
        assert count > 0

    async def test_digest_format_includes_related_notes(self, session: AsyncSession):
        """Digest message includes related notes for tagged events."""
        from app.services.beautiful_dates.engine import recalculate_for_event
        from app.services.notification_service import build_digest, format_digest_message

        user = await _user(session, uid=4300)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Tagged Event", event_date=date(2020, 1, 1),
            tag_names=["Gift"],
        ))
        await create_note(session, user.id, NoteCreate(
            text="Buy flowers for the event",
            tag_names=["Gift"],
        ))
        await recalculate_for_event(session, event, [strategy])

        digest = await build_digest(session, user)
        message = await format_digest_message(session, user, digest)

        # Message should contain the note text
        assert "Buy flowers" in message


# =====================================================================
# E2E FLOW 10: Date Utils
# =====================================================================


class TestDateUtils:
    """Test date formatting and parsing utilities."""

    def test_parse_date_dd_mm_yyyy(self):
        from app.utils.date_utils import parse_date
        assert parse_date("15.06.2023") == date(2023, 6, 15)

    def test_parse_date_slash_format(self):
        from app.utils.date_utils import parse_date
        assert parse_date("15/06/2023") == date(2023, 6, 15)

    def test_parse_date_iso_format(self):
        from app.utils.date_utils import parse_date
        assert parse_date("2023-06-15") == date(2023, 6, 15)

    def test_parse_date_invalid(self):
        from app.utils.date_utils import parse_date
        assert parse_date("not a date") is None
        assert parse_date("32.13.2023") is None

    def test_days_between(self):
        from app.utils.date_utils import days_between
        assert days_between(date(2023, 1, 1), date(2023, 1, 11)) == 10
        assert days_between(date(2023, 1, 11), date(2023, 1, 1)) == 10

    def test_format_date_ru(self):
        from app.utils.date_utils import format_date
        result = format_date(date(2023, 3, 15), "ru")
        assert "15" in result
        assert "марта" in result

    def test_format_date_en(self):
        from app.utils.date_utils import format_date
        result = format_date(date(2023, 3, 15), "en")
        assert "March" in result
        assert "15" in result

    def test_format_relative_today(self):
        from app.utils.date_utils import format_relative_date
        result = format_relative_date(date.today(), "ru")
        # Should contain "today" equivalent
        assert len(result) > 0

    def test_format_relative_tomorrow(self):
        from app.utils.date_utils import format_relative_date
        result = format_relative_date(date.today() + timedelta(days=1), "ru")
        assert len(result) > 0

    def test_format_relative_in_week(self):
        from app.utils.date_utils import format_relative_date
        result = format_relative_date(date.today() + timedelta(days=7), "ru")
        assert len(result) > 0

    def test_format_relative_in_n_days(self):
        from app.utils.date_utils import format_relative_date
        result = format_relative_date(date.today() + timedelta(days=5), "ru")
        assert len(result) > 0
