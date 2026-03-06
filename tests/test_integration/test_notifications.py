from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wish import Wish
from app.services.notification_service import (
    get_active_notifiable_users,
    get_dates_for_day,
    get_dates_for_range,
    get_due_wish_reminders,
    log_notification,
)


@pytest.fixture
async def active_user(session: AsyncSession) -> User:
    u = User(
        id=777888999,
        first_name="Notify",
        language="ru",
        is_active=True,
        notifications_enabled=True,
    )
    session.add(u)
    await session.flush()
    return u


@pytest.fixture
async def inactive_user(session: AsyncSession) -> User:
    u = User(
        id=777888998,
        first_name="Inactive",
        is_active=False,
        notifications_enabled=True,
    )
    session.add(u)
    await session.flush()
    return u


@pytest.fixture
async def disabled_notif_user(session: AsyncSession) -> User:
    u = User(
        id=777888997,
        first_name="NoNotif",
        is_active=True,
        notifications_enabled=False,
    )
    session.add(u)
    await session.flush()
    return u


class TestGetActiveNotifiableUsers:
    async def test_active_user_found(self, session, active_user):
        users = await get_active_notifiable_users(session)
        ids = [x.id for x in users]
        assert active_user.id in ids

    async def test_inactive_user_excluded(self, session, inactive_user):
        users = await get_active_notifiable_users(session)
        ids = [x.id for x in users]
        assert inactive_user.id not in ids

    async def test_disabled_notifications_excluded(self, session, disabled_notif_user):
        users = await get_active_notifiable_users(session)
        ids = [x.id for x in users]
        assert disabled_notif_user.id not in ids


class TestGetDatesForDay:
    async def test_empty_dates(self, session, active_user):
        dates = await get_dates_for_day(session, active_user.id, date.today())
        assert dates == []


class TestGetDatesForRange:
    async def test_empty_range(self, session, active_user):
        dates = await get_dates_for_range(
            session, active_user.id, date.today(), date.today() + timedelta(days=7)
        )
        assert dates == []


class TestDueWishReminders:
    async def test_reminder_due_tomorrow(self, session, active_user):
        tomorrow = date.today() + timedelta(days=1)
        wish = Wish(
            user_id=active_user.id,
            text="Reminder wish",
            reminder_date=tomorrow,
            reminder_sent=False,
        )
        session.add(wish)
        await session.flush()

        reminders = await get_due_wish_reminders(session, active_user)
        assert len(reminders) == 1
        assert reminders[0].text == "Reminder wish"

    async def test_already_sent_excluded(self, session, active_user):
        tomorrow = date.today() + timedelta(days=1)
        wish = Wish(
            user_id=active_user.id,
            text="Sent wish",
            reminder_date=tomorrow,
            reminder_sent=True,
        )
        session.add(wish)
        await session.flush()

        reminders = await get_due_wish_reminders(session, active_user)
        assert len(reminders) == 0

    async def test_reminder_not_due_yet(self, session, active_user):
        far_future = date.today() + timedelta(days=30)
        wish = Wish(
            user_id=active_user.id,
            text="Future wish",
            reminder_date=far_future,
            reminder_sent=False,
        )
        session.add(wish)
        await session.flush()

        reminders = await get_due_wish_reminders(session, active_user)
        assert len(reminders) == 0


class TestLogNotification:
    async def test_log_created(self, session, active_user):
        await log_notification(session, active_user.id, "digest")
