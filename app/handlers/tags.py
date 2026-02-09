"""Tag handlers — list, view, create, rename, delete, browse events/notes."""

import uuid
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import TagCreateStates, TagRenameStates
from app.i18n.loader import t
from app.keyboards.callbacks import EventCb, NoteCb, PageCb, TagCb
from app.keyboards.main_menu import cancel_kb
from app.keyboards.tags import PAGE_SIZE, tag_delete_confirm_kb, tag_view_kb, tags_list_kb
from app.models.event import EventTag
from app.models.note import NoteTag
from app.models.user import User
from app.services.event_service import get_events_by_tag_names
from app.services.note_service import get_notes_by_tag_names
from app.services.tag_service import (
    create_tag,
    delete_tag,
    get_tag,
    get_user_tags,
    rename_tag,
)

router = Router(name="tags")


# --- Shared display helpers ---


async def show_tags_list(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
    page: int = 0,
) -> None:
    all_tags = await get_user_tags(session, user.id)
    total = len(all_tags)
    start = page * PAGE_SIZE
    tags = all_tags[start : start + PAGE_SIZE]

    text = t("tags.empty", lang) if not tags and total == 0 else t("tags.title", lang)

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=tags_list_kb(tags, page, total, lang),
    )


# --- List ---


@router.callback_query(TagCb.filter(F.action == "list"))
async def tag_list(
    callback: CallbackQuery,
    callback_data: TagCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_tags_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


@router.callback_query(PageCb.filter(F.target == "tags"))
async def tag_page(
    callback: CallbackQuery,
    callback_data: PageCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_tags_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


# --- View ---


@router.callback_query(TagCb.filter(F.action == "view"))
async def tag_view(
    callback: CallbackQuery,
    callback_data: TagCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    tag = await get_tag(session, uuid.UUID(callback_data.id), user_id=user.id)
    if tag is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    # Count associated events and notes via queries (no lazy load in async)
    events_count = (await session.execute(
        select(func.count()).where(EventTag.tag_id == tag.id)
    )).scalar_one()
    notes_count = (await session.execute(
        select(func.count()).where(NoteTag.tag_id == tag.id)
    )).scalar_one()

    text = (
        f"<b>\U0001f3f7 {escape(tag.name)}</b>\n\n"
        f"{t('tags.events_count', lang, count=str(events_count))}\n"
        f"{t('tags.notes_count', lang, count=str(notes_count))}"
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=tag_view_kb(tag, lang, events_count=events_count, notes_count=notes_count),
    )
    await callback.answer()


# --- Browse events by tag ---


@router.callback_query(TagCb.filter(F.action == "events"))
async def tag_events(
    callback: CallbackQuery,
    callback_data: TagCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    tag = await get_tag(session, uuid.UUID(callback_data.id), user_id=user.id)
    if tag is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    events = await get_events_by_tag_names(session, user.id, [tag.name], limit=20)

    text = f"<b>\U0001f3f7 {escape(tag.name)} — {t('tags.show_events', lang)}</b>\n\n"
    if not events:
        text += t("events.empty", lang)
    else:
        for ev in events:
            text += f"\U0001f4c5 <b>{escape(ev.title)}</b> — {ev.event_date.strftime('%d.%m.%Y')}\n"

    # Build keyboard: event buttons + back to tag
    rows: list[list[InlineKeyboardButton]] = []
    for ev in events:
        rows.append([InlineKeyboardButton(
            text=f"\U0001f4c5 {ev.title}",
            callback_data=EventCb(action="view", id=str(ev.id)).pack(),
        )])
    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=TagCb(action="view", id=callback_data.id).pack(),
    )])

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


# --- Browse notes by tag ---


@router.callback_query(TagCb.filter(F.action == "notes"))
async def tag_notes(
    callback: CallbackQuery,
    callback_data: TagCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    tag = await get_tag(session, uuid.UUID(callback_data.id), user_id=user.id)
    if tag is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    notes = await get_notes_by_tag_names(session, user.id, [tag.name], limit=20)

    text = f"<b>\U0001f3f7 {escape(tag.name)} — {t('tags.show_notes', lang)}</b>\n\n"
    if not notes:
        text += t("notes.empty", lang)
    else:
        for nt in notes:
            preview = escape(nt.text[:50]) + ("..." if len(nt.text) > 50 else "")
            text += f"\U0001f4dd {preview}\n"

    # Build keyboard: note buttons + back to tag
    rows: list[list[InlineKeyboardButton]] = []
    for nt in notes:
        preview = nt.text[:40] + ("..." if len(nt.text) > 40 else "")
        rows.append([InlineKeyboardButton(
            text=f"\U0001f4dd {preview}",
            callback_data=NoteCb(action="view", id=str(nt.id)).pack(),
        )])
    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=TagCb(action="view", id=callback_data.id).pack(),
    )])

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


# --- Create ---


@router.callback_query(TagCb.filter(F.action == "create"))
async def tag_create_start(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("tags.create_name", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(TagCreateStates.waiting_name)
    await callback.answer()


@router.message(TagCreateStates.waiting_name)
async def tag_create_name(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer(t("errors.invalid_input", lang))
        return

    tag = await create_tag(session, user.id, name)
    await state.clear()
    await message.answer(
        t("tags.created", lang, name=escape(tag.name)),
        reply_markup=tag_view_kb(tag, lang),
    )


# --- Rename ---


@router.callback_query(TagCb.filter(F.action == "rename"))
async def tag_rename_start(
    callback: CallbackQuery,
    callback_data: TagCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(rename_tag_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("tags.rename_prompt", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(TagRenameStates.waiting_name)
    await callback.answer()


@router.message(TagRenameStates.waiting_name)
async def tag_rename_name(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    new_name = (message.text or "").strip()
    if not new_name:
        await message.answer(t("errors.invalid_input", lang))
        return

    tag = await rename_tag(
        session, uuid.UUID(data["rename_tag_id"]), new_name, user_id=user.id
    )
    await state.clear()

    if tag is None:
        from app.keyboards.main_menu import main_menu_kb
        await message.answer(
            t("tags.already_exists", lang, name=escape(new_name)),
            reply_markup=main_menu_kb(lang),
        )
        return

    await message.answer(
        t("tags.renamed", lang, name=escape(tag.name)),
        reply_markup=tag_view_kb(tag, lang),
    )


# --- Delete ---


@router.callback_query(TagCb.filter(F.action == "delete"))
async def tag_delete_ask(
    callback: CallbackQuery,
    callback_data: TagCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    tag = await get_tag(session, uuid.UUID(callback_data.id), user_id=user.id)
    if tag is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("tags.delete_confirm", lang, name=escape(tag.name)),
        reply_markup=tag_delete_confirm_kb(callback_data.id, lang),
    )
    await callback.answer()


@router.callback_query(TagCb.filter(F.action == "confirm_delete"))
async def tag_delete_confirm(
    callback: CallbackQuery,
    callback_data: TagCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await delete_tag(session, uuid.UUID(callback_data.id), user_id=user.id)
    await callback.answer(t("tags.deleted", lang))
    await show_tags_list(callback, user, lang, session)
