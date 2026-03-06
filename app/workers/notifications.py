import logging
from datetime import UTC, datetime

from aiogram.exceptions import TelegramForbiddenError

from app.database import async_session_factory
from app.services.notification_service import (
    build_digest,
    get_due_wish_reminders,
    get_users_for_notification,
    log_notification,
)

logger = logging.getLogger(__name__)


async def send_digest_task(ctx: dict, user_id: int, force: bool = False) -> bool:
    from datetime import date as date_type
    from html import escape

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from app.bot import bot
    from app.i18n.loader import t
    from app.keyboards.callbacks import EventCb, FeedCb, MenuCb
    from app.services.wish_service import get_wishes_by_person_names
    from app.utils.date_utils import format_relative_date

    async with async_session_factory() as session:
        from app.models.user import User
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            return False
        if not force and not user.notifications_enabled:
            return False

        lang = user.language
        dates = await build_digest(session, user)

        greeting = f"\u2600\ufe0f {t('notifications.morning_greeting', lang, name=user.first_name)}"
        if dates:
            greeting += f"\n{t('notifications.your_beautiful_dates', lang)}"
        else:
            greeting += f"\n{t('notifications.no_dates_today', lang)}"

        try:
            await bot.send_message(user_id, greeting)

            for bd in dates:
                label = bd.label_ru if lang == "ru" else bd.label_en
                delta_days = (bd.target_date - date_type.today()).days
                if 0 <= delta_days < 20:
                    relative = format_relative_date(bd.target_date, lang)
                    text = f"\U0001f52e <b>{relative} \u2014 {label}</b>\n"
                else:
                    text = f"\U0001f52e <b>{label}</b>\n"
                text += f"\U0001f4c5 {t('feed.when', lang)} {bd.target_date.strftime('%d.%m.%Y')}"

                if bd.event.people:
                    person_names = [x.name for x in bd.event.people]
                    wishes = await get_wishes_by_person_names(session, user.id, person_names, limit=50)
                    if wishes:
                        text += f"\n\n{t('feed.related_wishes', lang)}"
                        for x in wishes:
                            preview = escape(x.text[:60]) + ("..." if len(x.text) > 60 else "")
                            text += f"\n\u2014 {preview}"

                if user.spoiler_enabled:
                    text = f"<tg-spoiler>{text}</tg-spoiler>"

                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=f"\U0001f4c5 {t('feed.to_event', lang)}",
                        callback_data=EventCb(action="view_new", id=str(bd.event_id)).pack(),
                    ),
                    InlineKeyboardButton(
                        text=f"\U0001f517 {t('feed.share', lang)}",
                        callback_data=FeedCb(action="share", id=str(bd.id)).pack(),
                    ),
                ]])
                await bot.send_message(user_id, text, reply_markup=kb)

            closing_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"\U0001f4c5 {t('notifications.open_feed', lang)}",
                    callback_data=MenuCb(action="feed").pack(),
                )],
            ])
            await bot.send_message(
                user_id,
                t("notifications.closing", lang),
                reply_markup=closing_kb,
            )

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


async def send_wish_reminders_task(ctx: dict, user_id: int, force: bool = False) -> int:
    from app.bot import bot
    from app.i18n.loader import t

    sent = 0
    async with async_session_factory() as session:
        from app.models.user import User
        user = await session.get(User, user_id)
        if user is None or (not force and not user.is_active):
            return 0

        lang = user.language
        wishes = await get_due_wish_reminders(session, user)

        for wish in wishes:
            try:
                text = f"\U0001f514 {t('notifications.wish_reminder', lang)}\n\n{wish.text}"
                await bot.send_message(user_id, text)
                wish.reminder_sent = True
                await log_notification(session, user_id, "wish_reminder", wish_id=wish.id)
                sent += 1
            except TelegramForbiddenError:
                user.is_active = False
                break
            except Exception:
                logger.exception("Failed to send wish reminder to user %s", user_id)

        await session.commit()
    return sent


async def check_and_send_notifications(ctx: dict) -> int:
    now = datetime.now(tz=UTC)
    total_sent = 0

    async with async_session_factory() as session:
        users = await get_users_for_notification(session, now.hour, now.minute)

    for user in users:
        success = await send_digest_task(ctx, user.id)
        if success:
            total_sent += 1
        await send_wish_reminders_task(ctx, user.id)

    logger.info(
        "Notification check at %s: sent %d digests to %d eligible users",
        now.strftime("%H:%M"),
        total_sent,
        len(users),
    )
    return total_sent
