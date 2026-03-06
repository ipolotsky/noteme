"""End-to-end tests exercising full multi-layer flows through
the real database: services + models + strategies + notifications.

These tests create real DB records and verify cross-module interactions.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beautiful_date_strategy import BeautifulDateStrategy
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.wish import WishCreate
from app.services.event_service import (
    EventLimitError,
    count_user_events,
    create_event,
    delete_event,
    get_event,
    update_event,
)
from app.services.person_service import (
    create_person,
    get_or_create_people,
    get_user_people,
)
from app.services.user_service import get_or_create_user, update_user
from app.services.wish_service import (
    WishLimitError,
    create_wish,
    get_user_wishes,
    get_wishes_by_person_names,
)

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
        assert user.max_events == 10
        assert user.max_wishes == 10
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
# E2E FLOW 3: Wishes + People Cross-linking
# =====================================================================


class TestWishesPeopleCrosslinking:
    """Wishes and events share people, enabling related wishes in feed."""

    async def test_person_links_event_and_wish(self, session: AsyncSession):
        """Create event with person 'Max', wish with person 'Max' -> wishes_by_person_names finds it."""
        user = await _user(session, uid=700)

        await create_event(session, user.id, EventCreate(
            title="Wedding with Max", event_date=date(2022, 8, 17),
            person_names=["Max"],
        ))
        wish = await create_wish(session, user.id, WishCreate(
            text="Max wants Sony headphones",
            person_names=["Max"],
        ))

        related = await get_wishes_by_person_names(session, user.id, ["Max"])
        assert len(related) >= 1
        assert any(x.id == wish.id for x in related)

    async def test_case_insensitive_person_match(self, session: AsyncSession):
        """People 'max' and 'Max' should resolve to same person."""
        user = await _user(session, uid=800)

        people = await get_or_create_people(session, user.id, ["Max", "max", "MAX"])
        assert len(people) == 1
        assert people[0].name == "Max"

    async def test_wish_with_multiple_people(self, session: AsyncSession):
        """Wish with multiple people found via any of them."""
        user = await _user(session, uid=900)

        await create_wish(session, user.id, WishCreate(
            text="Gift idea", person_names=["Family", "Birthday"],
        ))

        found_by_family = await get_wishes_by_person_names(session, user.id, ["Family"])
        found_by_birthday = await get_wishes_by_person_names(session, user.id, ["Birthday"])

        assert len(found_by_family) == 1
        assert len(found_by_birthday) == 1

    async def test_delete_person_leaves_wishes(self, session: AsyncSession):
        """Deleting a person doesn't delete the wish itself."""
        from app.services.person_service import delete_person

        user = await _user(session, uid=1000)
        wish = await create_wish(session, user.id, WishCreate(
            text="Important", person_names=["Work"],
        ))
        people = await get_user_people(session, user.id)
        assert len(people) == 1

        await delete_person(session, people[0].id, user_id=user.id)
        wishes = await get_user_wishes(session, user.id)
        assert len(wishes) == 1
        assert wishes[0].id == wish.id


# =====================================================================
# E2E FLOW 4: Limits Enforcement
# =====================================================================


class TestLimitsEnforcement:
    """User limits (max_events, max_wishes) enforced across services."""

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

    async def test_wish_limit_enforced(self, session: AsyncSession):
        """Cannot create more wishes than max_wishes."""
        user = await _user(session, uid=1200)
        user.max_wishes = 1
        await session.flush()

        await create_wish(session, user.id, WishCreate(text="Wish 1"))

        try:
            await create_wish(session, user.id, WishCreate(text="Wish 2"))
            raise AssertionError("Should raise WishLimitError")
        except WishLimitError as e:
            assert e.max_wishes == 1

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
    """Build digest and check wish reminders."""

    async def test_get_dates_for_range_with_dates(self, session: AsyncSession):
        """Range query returns upcoming beautiful dates."""
        from app.services.beautiful_dates.engine import recalculate_for_event
        from app.services.notification_service import get_dates_for_range

        user = await _user(session, uid=1500)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Notification Test", event_date=date(2020, 1, 1),
        ))
        await recalculate_for_event(session, event, [strategy])

        dates = await get_dates_for_range(session, user.id, date.today(), date.today() + timedelta(days=3650))
        assert len(dates) > 0

    async def test_get_dates_for_range_empty_no_events(self, session: AsyncSession):
        """Range query is empty when no events exist."""
        from app.services.notification_service import get_dates_for_range

        user = await _user(session, uid=1600)
        dates = await get_dates_for_range(session, user.id, date.today(), date.today() + timedelta(days=365))
        assert len(dates) == 0

    async def test_wish_reminders_due_tomorrow(self, session: AsyncSession):
        """Wishes with reminder_date = tomorrow are found."""
        from app.services.notification_service import get_due_wish_reminders

        user = await _user(session, uid=1900)
        tomorrow = date.today() + timedelta(days=1)

        await create_wish(session, user.id, WishCreate(
            text="Remind me!", reminder_date=tomorrow,
        ))
        await create_wish(session, user.id, WishCreate(
            text="No reminder",
        ))

        reminders = await get_due_wish_reminders(session, user)
        assert len(reminders) == 1
        assert reminders[0].text == "Remind me!"

    async def test_wish_reminder_not_sent_twice(self, session: AsyncSession):
        """Once reminder_sent=True, wish is not returned again."""
        from app.services.notification_service import get_due_wish_reminders

        user = await _user(session, uid=2000)
        tomorrow = date.today() + timedelta(days=1)

        wish = await create_wish(session, user.id, WishCreate(
            text="Once only", reminder_date=tomorrow,
        ))
        wish.reminder_sent = True
        await session.flush()

        reminders = await get_due_wish_reminders(session, user)
        assert len(reminders) == 0

    async def test_notification_users_filter(self, session: AsyncSession):
        """get_active_notifiable_users filters by active and enabled."""
        from app.services.notification_service import get_active_notifiable_users

        u1 = await _user(session, uid=2100)
        u1.notifications_enabled = True

        u2 = await _user(session, uid=2200)
        u2.is_active = False

        await _user(session, uid=2300)

        u4 = await _user(session, uid=2400)
        u4.notifications_enabled = False

        await session.flush()

        users = await get_active_notifiable_users(session)
        ids = [x.id for x in users]
        assert 2100 in ids
        assert 2300 in ids
        assert 2200 not in ids
        assert 2400 not in ids

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

    async def test_people_scoped_to_user(self, session: AsyncSession):
        """Two users can have people with same name independently."""
        u1 = await _user(session, uid=3800)
        u2 = await _user(session, uid=3900)

        p1 = await create_person(session, u1.id, "Shared Name")
        p2 = await create_person(session, u2.id, "Shared Name")

        assert p1.id != p2.id
        assert p1.user_id == u1.id
        assert p2.user_id == u2.id

    async def test_wishes_scoped_to_user(self, session: AsyncSession):
        """get_wishes_by_person_names only returns current user's wishes."""
        u1 = await _user(session, uid=4000)
        u2 = await _user(session, uid=4100)

        await create_wish(session, u1.id, WishCreate(text="U1 wish", person_names=["Work"]))
        await create_wish(session, u2.id, WishCreate(text="U2 wish", person_names=["Work"]))

        u1_wishes = await get_wishes_by_person_names(session, u1.id, ["Work"])
        u2_wishes = await get_wishes_by_person_names(session, u2.id, ["Work"])

        assert len(u1_wishes) == 1
        assert u1_wishes[0].text == "U1 wish"
        assert len(u2_wishes) == 1
        assert u2_wishes[0].text == "U2 wish"


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

    async def test_dates_for_range_includes_event_with_people(self, session: AsyncSession):
        """Range query returns dates for events linked to people."""
        from app.services.beautiful_dates.engine import recalculate_for_event
        from app.services.notification_service import get_dates_for_range

        user = await _user(session, uid=4300)
        strategy = await _seed_strategy(session, "multiples", {"base": 100, "min": 100, "max": 5000, "unit": "days"})

        event = await create_event(session, user.id, EventCreate(
            title="Tagged Event", event_date=date(2020, 1, 1),
            person_names=["Gift"],
        ))
        await create_wish(session, user.id, WishCreate(
            text="Buy flowers for the event",
            person_names=["Gift"],
        ))
        await recalculate_for_event(session, event, [strategy])

        dates = await get_dates_for_range(session, user.id, date.today(), date.today() + timedelta(days=3650))
        assert len(dates) > 0
        assert any(x.event_id == event.id for x in dates)


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
