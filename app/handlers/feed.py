"""Feed handler — beautiful dates feed (each date as a separate message)."""

import uuid
from datetime import date as date_type
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.i18n.loader import t
from app.keyboards.callbacks import EventCb, FeedCb, MenuCb, PageCb
from app.keyboards.pagination import pagination_row
from app.models.user import User
from app.services.beautiful_date_service import (
    count_user_feed,
    generate_share_uuid,
    get_user_feed,
)
from app.services.note_service import get_notes_by_tag_names
from app.utils.date_utils import format_relative_date

router = Router(name="feed")

PAGE_SIZE = 5

_FSM_KEY = "feed_message_ids"

async def _delete_previous_feed(chat_id: int, state: FSMContext, bot) -> None:  # noqa: ANN001
    """Delete previously sent feed messages from chat."""
    data = await state.get_data()
    msg_ids = data.get(_FSM_KEY, [])
    for mid in msg_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    await state.update_data(**{_FSM_KEY: []})


async def _send_feed(
    chat_message: Message,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
    page: int = 0,
) -> bool:
    """Send feed dates as separate messages. Returns False if empty."""
    total = await count_user_feed(session, user.id)
    items = await get_user_feed(session, user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE)

    if not items:
        return False

    sent_ids: list[int] = []

    for bd in items:
        label = bd.label_ru if lang == "ru" else bd.label_en
        delta_days = (bd.target_date - date_type.today()).days
        if 0 <= delta_days < 20:
            relative = format_relative_date(bd.target_date, lang)
            text = f"\U0001f52e <b>{relative} — {label}</b>\n"
        else:
            text = f"\U0001f52e <b>{label}</b>\n"
        text += f"\U0001f4c5 {t('feed.when', lang)} {bd.target_date.strftime('%d.%m.%Y')}"

        if bd.event.tags:
            tag_names = [tg.name for tg in bd.event.tags]
            notes = await get_notes_by_tag_names(session, user.id, tag_names, limit=50)
            if notes:
                text += f"\n\n{t('feed.related_notes', lang)}"
                for note in notes:
                    preview = escape(note.text[:60]) + ("..." if len(note.text) > 60 else "")
                    text += f"\n— {preview}"

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
        msg = await chat_message.answer(text, reply_markup=kb)
        sent_ids.append(msg.message_id)

    # Navigation footer
    nav_rows: list[list[InlineKeyboardButton]] = []
    if total > PAGE_SIZE:
        nav_rows.append(pagination_row("feed", page, total, PAGE_SIZE, lang))
    nav_rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])
    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    nav_msg = await chat_message.answer(
        f"\U0001f52e {t('feed.title', lang)} ({page + 1}/{total_pages})",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=nav_rows),
    )
    sent_ids.append(nav_msg.message_id)

    # Save sent message IDs for cleanup on pagination
    await state.update_data(**{_FSM_KEY: sent_ids})

    return True


async def show_feed_list(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
    page: int = 0,
) -> None:
    """Show feed from a callback query (inline button press)."""
    # Delete previous feed messages
    await _delete_previous_feed(callback.message.chat.id, state, callback.bot)  # type: ignore[union-attr]

    sent = await _send_feed(callback.message, user, lang, session, state, page)  # type: ignore[arg-type]
    if not sent:
        from app.keyboards.main_menu import main_menu_kb

        await callback.message.edit_text(  # type: ignore[union-attr]
            t("feed.empty", lang),
            reply_markup=main_menu_kb(lang),
        )
        return

    # Delete the triggering menu message
    try:
        await callback.message.delete()  # type: ignore[union-attr]
    except Exception:
        pass


async def send_feed_messages(
    message: Message,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
    page: int = 0,
) -> None:
    """Send feed from a plain message context (reply keyboard)."""
    from app.keyboards.main_menu import main_menu_kb

    # Delete previous feed messages
    await _delete_previous_feed(message.chat.id, state, message.bot)

    sent = await _send_feed(message, user, lang, session, state, page)
    if not sent:
        await message.answer(t("feed.empty", lang), reply_markup=main_menu_kb(lang))


# --- List ---


@router.callback_query(FeedCb.filter(F.action == "list"))
async def feed_list(
    callback: CallbackQuery,
    callback_data: FeedCb,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await show_feed_list(callback, user, lang, session, state, page=callback_data.page)
    await callback.answer()


@router.callback_query(PageCb.filter(F.target == "feed"))
async def feed_page(
    callback: CallbackQuery,
    callback_data: PageCb,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await show_feed_list(callback, user, lang, session, state, page=callback_data.page)
    await callback.answer()


# --- Share ---


@router.callback_query(FeedCb.filter(F.action == "share"))
async def feed_share(
    callback: CallbackQuery,
    callback_data: FeedCb,
    lang: str,
    session: AsyncSession,
) -> None:
    share_uuid = await generate_share_uuid(session, uuid.UUID(callback_data.id))
    if share_uuid is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    url = f"{settings.app_base_url}/share/{share_uuid}"
    await callback.message.answer(  # type: ignore[union-attr]
        t("feed.shared_link", lang, url=url),
    )
    await callback.answer()
