import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramForbiddenError

from app.database import async_session_factory
from app.services.notification_service import (
    get_active_notifiable_users,
    get_dates_for_day,
    get_dates_for_range,
    log_notification,
)

logger = logging.getLogger(__name__)


async def _send_date_card(
    bot, user_id: int, bd, lang: str, spoiler: bool, session
) -> None:
    from html import escape

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from app.keyboards.callbacks import EventCb, FeedCb
    from app.services.wish_service import get_wishes_by_person_names
    from app.utils.date_utils import format_relative_date

    label = bd.label_ru if lang == "ru" else bd.label_en
    delta_days = (bd.target_date - date.today()).days
    if 0 <= delta_days < 20:
        relative = format_relative_date(bd.target_date, lang)
        text = f"\U0001f52e <b>{relative} \u2014 {label}</b>\n"
    else:
        text = f"\U0001f52e <b>{label}</b>\n"
    text += f"\U0001f4c5 {bd.target_date.strftime('%d.%m.%Y')}"

    if bd.event.people:
        person_names = [x.name for x in bd.event.people]
        wishes = await get_wishes_by_person_names(session, user_id, person_names, limit=50)
        if wishes:
            from app.i18n.loader import t
            text += f"\n\n{t('feed.related_wishes', lang)}"
            for x in wishes:
                preview = escape(x.text[:60]) + ("..." if len(x.text) > 60 else "")
                text += f"\n\u2014 {preview}"

    if spoiler:
        text = f"<tg-spoiler>{text}</tg-spoiler>"

    from app.i18n.loader import t
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


async def send_day_before_notification(ctx: dict, user_id: int, force: bool = False) -> bool:
    from app.bot import bot

    async with async_session_factory() as session:
        from app.models.user import User
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            return False
        if not force and (not user.notifications_enabled or not user.notify_day_before):
            return False

        lang = user.language
        tomorrow = date.today() + timedelta(days=1)
        dates = await get_dates_for_day(session, user.id, tomorrow)
        if not dates:
            return False

        try:
            from app.i18n.loader import t
            header = f"\U0001f514 {t('notifications.day_before', lang)}"
            await bot.send_message(user_id, header)

            for bd in dates:
                await _send_date_card(bot, user_id, bd, lang, user.spoiler_enabled, session)

            await log_notification(session, user_id, "day_before")
            await session.commit()
            return True
        except TelegramForbiddenError:
            logger.info("User %s blocked the bot, deactivating", user_id)
            user.is_active = False
            await session.commit()
            return False
        except Exception:
            logger.exception("Failed to send day_before to user %s", user_id)
            return False


async def send_week_before_notification(ctx: dict, user_id: int, force: bool = False) -> bool:
    from app.bot import bot

    async with async_session_factory() as session:
        from app.models.user import User
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            return False
        if not force and (not user.notifications_enabled or not user.notify_week_before):
            return False

        lang = user.language
        week_later = date.today() + timedelta(days=7)
        dates = await get_dates_for_day(session, user.id, week_later)
        if not dates:
            return False

        try:
            from app.i18n.loader import t
            header = f"\U0001f514 {t('notifications.week_before', lang)}"
            await bot.send_message(user_id, header)

            for bd in dates:
                await _send_date_card(bot, user_id, bd, lang, user.spoiler_enabled, session)

            await log_notification(session, user_id, "week_before")
            await session.commit()
            return True
        except TelegramForbiddenError:
            logger.info("User %s blocked the bot, deactivating", user_id)
            user.is_active = False
            await session.commit()
            return False
        except Exception:
            logger.exception("Failed to send week_before to user %s", user_id)
            return False


async def send_weekly_digest_notification(ctx: dict, user_id: int, force: bool = False) -> bool:
    from app.bot import bot

    async with async_session_factory() as session:
        from app.models.user import User
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            return False
        if not force and (not user.notifications_enabled or not user.notify_weekly_digest):
            return False

        lang = user.language
        today = date.today()
        end = today + timedelta(days=7)
        dates = await get_dates_for_range(session, user.id, today, end)
        if not dates:
            return False

        try:
            from app.i18n.loader import t
            header = f"\U0001f4c5 {t('notifications.weekly_greeting', lang)}"
            await bot.send_message(user_id, header)

            for bd in dates:
                await _send_date_card(bot, user_id, bd, lang, user.spoiler_enabled, session)

            await log_notification(session, user_id, "weekly_digest")
            await session.commit()
            return True
        except TelegramForbiddenError:
            logger.info("User %s blocked the bot, deactivating", user_id)
            user.is_active = False
            await session.commit()
            return False
        except Exception:
            logger.exception("Failed to send weekly_digest to user %s", user_id)
            return False


async def check_and_send_notifications(ctx: dict) -> int:
    now_utc = datetime.now(tz=UTC)
    total_sent = 0

    async with async_session_factory() as session:
        users = await get_active_notifiable_users(session)

    for user in users:
        try:
            local_now = now_utc.astimezone(ZoneInfo(user.timezone))
        except Exception:
            logger.warning("Invalid timezone %r for user %s, skipping", user.timezone, user.id)
            continue

        local_time = local_now.time().replace(second=0, microsecond=0)
        local_weekday = local_now.weekday()

        if user.notify_day_before and local_time == user.notify_day_before_time:
            success = await send_day_before_notification(ctx, user.id)
            if success:
                total_sent += 1

        if user.notify_week_before and local_time == user.notify_week_before_time:
            success = await send_week_before_notification(ctx, user.id)
            if success:
                total_sent += 1

        if (
            user.notify_weekly_digest
            and local_weekday == user.weekly_digest_day
            and local_time == user.weekly_digest_time
        ):
            success = await send_weekly_digest_notification(ctx, user.id)
            if success:
                total_sent += 1

    logger.info(
        "Notification check at %s UTC: sent %d notifications to %d eligible users",
        now_utc.strftime("%H:%M"),
        total_sent,
        len(users),
    )
    return total_sent
