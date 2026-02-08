"""Tests for notification service."""

from datetime import date, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.models.user import User
from app.services.notification_service import (
    build_digest,
    get_due_note_reminders,
    get_users_for_notification,
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
        notification_time=time(9, 0),
        notification_count=3,
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
        notification_time=time(9, 0),
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
        notification_time=time(9, 0),
    )
    session.add(u)
    await session.flush()
    return u


class TestGetUsersForNotification:
    async def test_active_user_found(self, session, active_user):
        users = await get_users_for_notification(session, 9, 0)
        ids = [u.id for u in users]
        assert active_user.id in ids

    async def test_inactive_user_excluded(self, session, inactive_user):
        users = await get_users_for_notification(session, 9, 0)
        ids = [u.id for u in users]
        assert inactive_user.id not in ids

    async def test_disabled_notifications_excluded(self, session, disabled_notif_user):
        users = await get_users_for_notification(session, 9, 0)
        ids = [u.id for u in users]
        assert disabled_notif_user.id not in ids

    async def test_wrong_time_excluded(self, session, active_user):
        users = await get_users_for_notification(session, 10, 0)  # Active user is at 9:00
        ids = [u.id for u in users]
        assert active_user.id not in ids


class TestBuildDigest:
    async def test_empty_digest(self, session, active_user):
        """User with no events gets empty digest."""
        dates = await build_digest(session, active_user)
        assert dates == []


class TestDueNoteReminders:
    async def test_reminder_due_tomorrow(self, session, active_user):
        tomorrow = date.today() + timedelta(days=1)
        note = Note(
            user_id=active_user.id,
            text="Reminder note",
            reminder_date=tomorrow,
            reminder_sent=False,
        )
        session.add(note)
        await session.flush()

        reminders = await get_due_note_reminders(session, active_user)
        assert len(reminders) == 1
        assert reminders[0].text == "Reminder note"

    async def test_already_sent_excluded(self, session, active_user):
        tomorrow = date.today() + timedelta(days=1)
        note = Note(
            user_id=active_user.id,
            text="Sent note",
            reminder_date=tomorrow,
            reminder_sent=True,
        )
        session.add(note)
        await session.flush()

        reminders = await get_due_note_reminders(session, active_user)
        assert len(reminders) == 0

    async def test_reminder_not_due_yet(self, session, active_user):
        far_future = date.today() + timedelta(days=30)
        note = Note(
            user_id=active_user.id,
            text="Future note",
            reminder_date=far_future,
            reminder_sent=False,
        )
        session.add(note)
        await session.flush()

        reminders = await get_due_note_reminders(session, active_user)
        assert len(reminders) == 0


class TestLogNotification:
    async def test_log_created(self, session, active_user):
        await log_notification(session, active_user.id, "digest")
        # Should not raise — just verify it doesn't crash
