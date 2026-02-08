"""Notification service — build daily digest, note reminders."""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.beautiful_date import BeautifulDate
from app.models.event import Event
from app.models.note import Note
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.services.note_service import get_notes_by_tag_names

logger = logging.getLogger(__name__)


async def build_digest(session: AsyncSession, user: User) -> list[BeautifulDate]:
    """Get upcoming beautiful dates for the user's daily digest."""
    today = date.today()
    result = await session.execute(
        select(BeautifulDate)
        .join(Event, BeautifulDate.event_id == Event.id)
        .options(
            selectinload(BeautifulDate.event).selectinload(Event.tags),
            selectinload(BeautifulDate.strategy),
        )
        .where(
            Event.user_id == user.id,
            BeautifulDate.target_date >= today,
        )
        .order_by(BeautifulDate.target_date.asc())
        .limit(user.notification_count)
    )
    return list(result.scalars().unique().all())


async def get_due_note_reminders(session: AsyncSession, user: User) -> list[Note]:
    """Get notes with reminders due tomorrow."""
    from datetime import timedelta
    tomorrow = date.today() + timedelta(days=1)
    result = await session.execute(
        select(Note)
        .where(
            Note.user_id == user.id,
            Note.reminder_date == tomorrow,
            Note.reminder_sent.is_(False),
        )
    )
    return list(result.scalars().all())


async def format_digest_message(
    session: AsyncSession, user: User, dates: list[BeautifulDate]
) -> str:
    """Format the daily digest message with beautiful dates and related notes."""
    from app.i18n.loader import t
    from app.utils.date_utils import format_relative_date

    lang = user.language
    lines: list[str] = []

    lines.append(f"\u2600\ufe0f {t('notifications.morning_greeting', lang, name=user.first_name)}")
    lines.append("")

    if not dates:
        lines.append(t("notifications.no_dates_today", lang))
    else:
        lines.append(t("notifications.your_beautiful_dates", lang))
        lines.append("")

        for bd in dates:
            label = bd.label_ru if lang == "ru" else bd.label_en
            relative = format_relative_date(bd.target_date, lang)
            line = f"\U0001f52e {relative} \u2014 {label}"

            if user.spoiler_enabled:
                line = f"||{line}||"

            lines.append(line)

            # Related notes
            if bd.event.tags:
                tag_names = [tg.name for tg in bd.event.tags]
                notes = await get_notes_by_tag_names(session, user.id, tag_names, limit=2)
                for note in notes:
                    preview = note.text[:60] + ("..." if len(note.text) > 60 else "")
                    lines.append(f"   \U0001f4dd {preview}")

            lines.append("")

    return "\n".join(lines)


async def log_notification(
    session: AsyncSession,
    user_id: int,
    notification_type: str,
    beautiful_date_id=None,
    note_id=None,
) -> None:
    """Log a sent notification."""
    log = NotificationLog(
        user_id=user_id,
        notification_type=notification_type,
        beautiful_date_id=beautiful_date_id,
        note_id=note_id,
    )
    session.add(log)
    await session.flush()


async def get_users_for_notification(
    session: AsyncSession, notification_hour: int, notification_minute: int
) -> list[User]:
    """Get active users whose notification_time matches the given hour:minute."""
    from datetime import time

    target_time = time(notification_hour, notification_minute)
    result = await session.execute(
        select(User).where(
            User.is_active.is_(True),
            User.notifications_enabled.is_(True),
            User.notification_time == target_time,
        )
    )
    return list(result.scalars().all())
