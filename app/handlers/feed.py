"""Feed handler — beautiful dates feed."""

import uuid
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.i18n.loader import t
from app.keyboards.callbacks import FeedCb, PageCb
from app.keyboards.feed import PAGE_SIZE, feed_item_kb, feed_list_kb
from app.models.user import User
from app.services.beautiful_date_service import (
    count_user_feed,
    generate_share_uuid,
    get_user_feed,
)
from app.services.note_service import get_notes_by_tag_names
from app.utils.date_utils import format_relative_date

router = Router(name="feed")


async def show_feed_list(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
    page: int = 0,
) -> None:
    total = await count_user_feed(session, user.id)
    items = await get_user_feed(session, user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE)

    if not items:
        from app.keyboards.main_menu import main_menu_kb
        await callback.message.edit_text(  # type: ignore[union-attr]
            t("feed.empty", lang),
            reply_markup=main_menu_kb(lang),
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("feed.title", lang),
        reply_markup=feed_list_kb(items, page, total, lang),
    )


# --- List ---


@router.callback_query(FeedCb.filter(F.action == "list"))
async def feed_list(
    callback: CallbackQuery,
    callback_data: FeedCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_feed_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


@router.callback_query(PageCb.filter(F.target == "feed"))
async def feed_page(
    callback: CallbackQuery,
    callback_data: PageCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_feed_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


# --- View ---


@router.callback_query(FeedCb.filter(F.action == "view"))
async def feed_view(
    callback: CallbackQuery,
    callback_data: FeedCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.beautiful_date import BeautifulDate
    from app.models.event import Event

    result = await session.execute(
        select(BeautifulDate)
        .options(
            selectinload(BeautifulDate.event).selectinload(Event.tags),
        )
        .where(BeautifulDate.id == uuid.UUID(callback_data.id))
    )
    bd = result.scalar_one_or_none()

    if bd is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    label = bd.label_ru if lang == "ru" else bd.label_en
    relative = format_relative_date(bd.target_date, lang)
    text = f"\U0001f52e <b>{relative} — {label}</b>\n\n"
    text += f"\U0001f4c5 {bd.target_date.strftime('%d.%m.%Y')}\n"
    text += f"\U0001f4cb {escape(bd.event.title)}"

    # Related notes
    if bd.event.tags:
        tag_names = [tg.name for tg in bd.event.tags]
        notes = await get_notes_by_tag_names(session, user.id, tag_names, limit=5)
        if notes:
            text += f"\n\n{t('feed.related_notes', lang)}"
            for note in notes:
                preview = escape(note.text[:60]) + ("..." if len(note.text) > 60 else "")
                text += f"\n\U0001f4dd {preview}"

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=feed_item_kb(bd, lang),
    )
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
