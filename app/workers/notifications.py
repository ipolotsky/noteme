"""arq tasks for notifications — daily digest + note reminders."""

import logging
from datetime import UTC, datetime

from aiogram.exceptions import TelegramForbiddenError

from app.database import async_session_factory
from app.services.notification_service import (
    build_digest,
    format_digest_message,
    get_due_note_reminders,
    get_users_for_notification,
    log_notification,
)

logger = logging.getLogger(__name__)


async def send_digest_task(ctx: dict, user_id: int) -> bool:
    """Send daily digest to a single user."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from app.bot import bot
    from app.i18n.loader import t
    from app.keyboards.callbacks import MenuCb

    async with async_session_factory() as session:
        from app.models.user import User
        user = await session.get(User, user_id)
        if user is None or not user.is_active or not user.notifications_enabled:
            return False

        lang = user.language
        dates = await build_digest(session, user)
        message = await format_digest_message(session, user, dates)

        # Add "Open feed" button
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"\U0001f4c5 {t('notifications.open_feed', lang)}",
                callback_data=MenuCb(action="feed").pack(),
            )],
        ])

        try:
            await bot.send_message(user_id, message, reply_markup=kb)
            await log_notification(session, user_id, "digest")
            await session.commit()
            return True
        except TelegramForbiddenError:
            logger.info("User %s blocked the bot, deactivating", user_id)
            user.is_active = False
            await session.commit()
            return False
        except Exception:
            logger.exception("Failed to send digest to user %s", user_id)
            return False


async def send_note_reminders_task(ctx: dict, user_id: int) -> int:
    """Send note reminders for a user."""
    from app.bot import bot
    from app.i18n.loader import t

    sent = 0
    async with async_session_factory() as session:
        from app.models.user import User
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            return 0

        lang = user.language
        notes = await get_due_note_reminders(session, user)

        for note in notes:
            try:
                text = f"\U0001f514 {t('notifications.note_reminder', lang)}\n\n{note.text}"
                await bot.send_message(user_id, text)
                note.reminder_sent = True
                await log_notification(session, user_id, "note_reminder", note_id=note.id)
                sent += 1
            except TelegramForbiddenError:
                user.is_active = False
                break
            except Exception:
                logger.exception("Failed to send note reminder to user %s", user_id)

        await session.commit()
    return sent


async def check_and_send_notifications(ctx: dict) -> int:
    """Cron job: check current minute and send notifications to matching users."""
    now = datetime.now(tz=UTC)
    total_sent = 0

    async with async_session_factory() as session:
        users = await get_users_for_notification(session, now.hour, now.minute)

    for user in users:
        success = await send_digest_task(ctx, user.id)
        if success:
            total_sent += 1
        # Also check note reminders
        await send_note_reminders_task(ctx, user.id)

    logger.info(
        "Notification check at %s: sent %d digests to %d eligible users",
        now.strftime("%H:%M"),
        total_sent,
        len(users),
    )
    return total_sent
