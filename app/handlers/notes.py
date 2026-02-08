"""Note handlers — list, view, create, edit, delete."""

import uuid
from datetime import datetime
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import NoteCreateStates, NoteEditStates
from app.i18n.loader import t
from app.keyboards.callbacks import NoteCb, NoteEditCb, PageCb
from app.keyboards.main_menu import cancel_kb
from app.keyboards.notes import (
    PAGE_SIZE,
    note_delete_confirm_kb,
    note_edit_kb,
    note_skip_kb,
    note_view_kb,
    notes_list_kb,
)
from app.models.user import User
from app.schemas.note import NoteCreate, NoteUpdate
from app.services.note_service import (
    NoteLimitError,
    count_user_notes,
    create_note,
    delete_note,
    get_note,
    get_user_notes,
    update_note,
)

router = Router(name="notes")


# --- Shared display helpers ---


async def show_notes_list(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
    page: int = 0,
) -> None:
    total = await count_user_notes(session, user.id)
    notes = await get_user_notes(session, user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE)

    text = t("notes.empty", lang) if not notes and total == 0 else t("notes.title", lang)

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=notes_list_kb(notes, page, total, lang),
    )


# --- List ---


@router.callback_query(NoteCb.filter(F.action == "list"))
async def note_list(
    callback: CallbackQuery,
    callback_data: NoteCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_notes_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


@router.callback_query(PageCb.filter(F.target == "notes"))
async def note_page(
    callback: CallbackQuery,
    callback_data: PageCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_notes_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


# --- View ---


@router.callback_query(NoteCb.filter(F.action == "view"))
async def note_view(
    callback: CallbackQuery,
    callback_data: NoteCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    note = await get_note(session, uuid.UUID(callback_data.id), user_id=user.id)
    if note is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    tags_str = ", ".join(escape(tg.name) for tg in note.tags) if note.tags else t("notes.no_tags", lang)
    text = (
        f"<b>{t('notes.view_title', lang)}</b>\n\n"
        f"{escape(note.text)}\n\n"
        f"{t('notes.tags_label', lang, tags=tags_str)}"
    )
    if note.reminder_date:
        text += f"\n{t('notes.reminder_set', lang, date=note.reminder_date.strftime('%d.%m.%Y'))}"

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=note_view_kb(note, lang),
    )
    await callback.answer()


# --- Create ---


@router.callback_query(NoteCb.filter(F.action == "create"))
async def note_create_start(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("notes.create_text", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(NoteCreateStates.waiting_text)
    await callback.answer()


@router.message(NoteCreateStates.waiting_text)
async def note_create_text(
    message: Message,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(text=message.text)
    await message.answer(
        t("notes.create_reminder", lang),
        reply_markup=note_skip_kb(lang),
    )
    await state.set_state(NoteCreateStates.waiting_reminder)


@router.message(NoteCreateStates.waiting_reminder)
async def note_create_reminder(
    message: Message,
    state: FSMContext,
    lang: str,
) -> None:
    try:
        reminder_date = datetime.strptime(message.text or "", "%d.%m.%Y").date()
        await state.update_data(reminder_date=reminder_date.isoformat())
    except ValueError:
        await message.answer(t("events.invalid_date", lang))
        return

    await message.answer(
        t("notes.create_tags", lang),
        reply_markup=note_skip_kb(lang),
    )
    await state.set_state(NoteCreateStates.waiting_tags)


@router.callback_query(NoteCreateStates.waiting_reminder, F.data == "skip")
async def note_create_skip_reminder(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("notes.create_tags", lang),
        reply_markup=note_skip_kb(lang),
    )
    await state.set_state(NoteCreateStates.waiting_tags)
    await callback.answer()


@router.message(NoteCreateStates.waiting_tags)
async def note_create_tags(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    tag_names = [tg.strip() for tg in (message.text or "").split(",") if tg.strip()]
    await _finish_note_create(message, state, user, lang, session, data, tag_names)


@router.callback_query(NoteCreateStates.waiting_tags, F.data == "skip")
async def note_create_skip_tags(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    await _finish_note_create(callback.message, state, user, lang, session, data, [])  # type: ignore[arg-type]
    await callback.answer()


async def _finish_note_create(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
    data: dict,
    tag_names: list[str],
) -> None:
    from datetime import date as date_type

    reminder_date = None
    if data.get("reminder_date"):
        reminder_date = date_type.fromisoformat(data["reminder_date"])

    note_data = NoteCreate(
        text=data["text"],
        reminder_date=reminder_date,
        tag_names=tag_names or [],
    )

    try:
        note = await create_note(session, user.id, note_data)
    except NoteLimitError:
        await message.answer(t("notes.limit_reached", lang, max=str(user.max_notes)))
        await state.clear()
        return

    await state.clear()
    await message.answer(
        t("notes.created", lang),
        reply_markup=note_view_kb(note, lang),
    )


# --- Edit ---


@router.callback_query(NoteCb.filter(F.action == "edit"))
async def note_edit_start(
    callback: CallbackQuery,
    callback_data: NoteCb,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("notes.edit", lang),
        reply_markup=note_edit_kb(callback_data.id, lang),
    )
    await callback.answer()


@router.callback_query(NoteEditCb.filter(F.field == "text"))
async def note_edit_text_start(
    callback: CallbackQuery,
    callback_data: NoteEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_note_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("notes.create_text", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(NoteEditStates.waiting_text)
    await callback.answer()


@router.message(NoteEditStates.waiting_text)
async def note_edit_text(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    note = await update_note(
        session, uuid.UUID(data["edit_note_id"]), NoteUpdate(text=message.text),
        user_id=user.id,
    )
    await state.clear()
    if note:
        await message.answer(
            t("notes.updated", lang),
            reply_markup=note_view_kb(note, lang),
        )
    else:
        await message.answer(t("errors.not_found", lang))


@router.callback_query(NoteEditCb.filter(F.field == "reminder"))
async def note_edit_reminder_start(
    callback: CallbackQuery,
    callback_data: NoteEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_note_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("notes.create_reminder", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(NoteEditStates.waiting_reminder)
    await callback.answer()


@router.message(NoteEditStates.waiting_reminder)
async def note_edit_reminder(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    try:
        reminder_date = datetime.strptime(message.text or "", "%d.%m.%Y").date()
    except ValueError:
        await message.answer(t("events.invalid_date", lang))
        return

    data = await state.get_data()
    note = await update_note(
        session, uuid.UUID(data["edit_note_id"]), NoteUpdate(reminder_date=reminder_date),
        user_id=user.id,
    )
    await state.clear()
    if note:
        await message.answer(
            t("notes.updated", lang),
            reply_markup=note_view_kb(note, lang),
        )
    else:
        await message.answer(t("errors.not_found", lang))


@router.callback_query(NoteEditCb.filter(F.field == "tags"))
async def note_edit_tags_start(
    callback: CallbackQuery,
    callback_data: NoteEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_note_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("notes.create_tags", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(NoteEditStates.waiting_tags)
    await callback.answer()


@router.message(NoteEditStates.waiting_tags)
async def note_edit_tags(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    tag_names = [tg.strip() for tg in (message.text or "").split(",") if tg.strip()]
    note = await update_note(
        session, uuid.UUID(data["edit_note_id"]), NoteUpdate(tag_names=tag_names),
        user_id=user.id,
    )
    await state.clear()
    if note:
        await message.answer(
            t("notes.updated", lang),
            reply_markup=note_view_kb(note, lang),
        )
    else:
        await message.answer(t("errors.not_found", lang))


# --- Delete ---


@router.callback_query(NoteCb.filter(F.action == "delete"))
async def note_delete_ask(
    callback: CallbackQuery,
    callback_data: NoteCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    note = await get_note(session, uuid.UUID(callback_data.id), user_id=user.id)
    if note is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("notes.delete_confirm", lang),
        reply_markup=note_delete_confirm_kb(callback_data.id, lang),
    )
    await callback.answer()


@router.callback_query(NoteCb.filter(F.action == "confirm_delete"))
async def note_delete_confirm(
    callback: CallbackQuery,
    callback_data: NoteCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await delete_note(session, uuid.UUID(callback_data.id), user_id=user.id)
    await callback.answer(t("notes.deleted", lang))
    await show_notes_list(callback, user, lang, session)
