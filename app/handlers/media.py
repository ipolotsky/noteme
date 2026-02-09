"""Media handlers — photo/video/video_note/document → note with tag."""

import uuid
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyParameters
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import MediaNoteStates
from app.i18n.loader import t
from app.keyboards.callbacks import MediaTagCb
from app.keyboards.notes import note_view_kb
from app.keyboards.tags import media_tag_select_kb
from app.models.user import User
from app.services.note_service import NoteLimitError, create_note_with_media
from app.services.tag_service import get_tag, get_user_tags

router = Router(name="media")

_MEDIA_TYPE_NAMES = {
    "photo": {"ru": "Фото", "en": "Photo"},
    "video": {"ru": "Видео", "en": "Video"},
    "video_note": {"ru": "Кружок", "en": "Circle"},
    "document": {"ru": "Файл", "en": "File"},
}


def _media_note_text(media_type: str, lang: str, caption: str | None = None) -> str:
    names = _MEDIA_TYPE_NAMES.get(media_type, {"ru": "Медиа", "en": "Media"})
    text = names.get(lang, names["en"])
    if caption:
        text += f"\n\n{caption}"
    return text


# --- Incoming media ---


@router.message(F.photo | F.video | F.video_note | F.document)
async def handle_media(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    # Detect media type
    if message.photo:
        media_type = "photo"
    elif message.video:
        media_type = "video"
    elif message.video_note:
        media_type = "video_note"
    elif message.document:
        media_type = "document"
    else:
        return

    # Store media info in FSM (include caption for note description)
    await state.update_data(
        media_chat_id=message.chat.id,
        media_message_id=message.message_id,
        media_type=media_type,
        media_caption=message.caption or "",
    )

    # Fetch user's existing tags
    tags = await get_user_tags(session, user.id)

    if not tags:
        await message.answer(t("media.no_tags", lang))
        return

    await message.answer(
        t("media.choose_tag", lang),
        reply_markup=media_tag_select_kb(tags, lang),
    )
    await state.set_state(MediaNoteStates.waiting_tag)


# --- Tag selection ---


@router.callback_query(MediaNoteStates.waiting_tag, MediaTagCb.filter(F.action == "select"))
async def media_tag_selected(
    callback: CallbackQuery,
    callback_data: MediaTagCb,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    tag = await get_tag(session, uuid.UUID(callback_data.id), user_id=user.id)
    if tag is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    note_text = _media_note_text(data["media_type"], lang, data.get("media_caption"))

    try:
        note = await create_note_with_media(
            session,
            user_id=user.id,
            text=note_text,
            tag_names=[tag.name],
            chat_id=data["media_chat_id"],
            message_id=data["media_message_id"],
            media_type=data["media_type"],
        )
    except NoteLimitError:
        await callback.message.edit_text(  # type: ignore[union-attr]
            t("notes.limit_reached", lang, max=str(user.max_notes))
        )
        await state.clear()
        await callback.answer()
        return

    await state.clear()

    tags_str = escape(tag.name)
    card = (
        f"<b>{t('notes.view_title', lang)}</b>\n\n"
        f"{escape(note.text)}\n\n"
        f"{t('notes.tags_label', lang, tags=tags_str)}"
    )
    # Delete tag selection message and reply to the original media
    try:
        await callback.message.delete()  # type: ignore[union-attr]
    except Exception:
        pass
    await callback.bot.send_message(  # type: ignore[union-attr]
        chat_id=data["media_chat_id"],
        text=card,
        reply_markup=note_view_kb(note, lang),
        reply_parameters=ReplyParameters(
            message_id=data["media_message_id"],
            allow_sending_without_reply=True,
        ),
    )
    await callback.answer()


# --- Create new tag for media ---


@router.callback_query(MediaNoteStates.waiting_tag, MediaTagCb.filter(F.action == "create"))
async def media_create_tag(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("media.create_tag_first", lang)
    )
    await state.set_state(MediaNoteStates.waiting_new_tag_name)
    await callback.answer()


@router.message(MediaNoteStates.waiting_new_tag_name)
async def media_new_tag_name(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    tag_name = (message.text or "").strip()
    if not tag_name:
        await message.answer(t("errors.invalid_input", lang))
        return

    data = await state.get_data()
    note_text = _media_note_text(data["media_type"], lang, data.get("media_caption"))

    try:
        note = await create_note_with_media(
            session,
            user_id=user.id,
            text=note_text,
            tag_names=[tag_name],
            chat_id=data["media_chat_id"],
            message_id=data["media_message_id"],
            media_type=data["media_type"],
        )
    except NoteLimitError:
        await message.answer(
            t("notes.limit_reached", lang, max=str(user.max_notes))
        )
        await state.clear()
        return

    await state.clear()

    tags_str = escape(tag_name)
    card = (
        f"<b>{t('notes.view_title', lang)}</b>\n\n"
        f"{escape(note.text)}\n\n"
        f"{t('notes.tags_label', lang, tags=tags_str)}"
    )
    # Reply to the original media message so user sees what was saved
    await message.bot.send_message(  # type: ignore[union-attr]
        chat_id=data["media_chat_id"],
        text=card,
        reply_markup=note_view_kb(note, lang),
        reply_parameters=ReplyParameters(
            message_id=data["media_message_id"],
            allow_sending_without_reply=True,
        ),
    )


# --- Cancel ---


@router.callback_query(MediaNoteStates.waiting_tag, MediaTagCb.filter(F.action == "cancel"))
async def media_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await state.clear()
    await callback.message.delete()  # type: ignore[union-attr]
    await callback.answer()
