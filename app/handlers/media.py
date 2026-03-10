import contextlib
import uuid
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyParameters
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import MediaWishStates
from app.i18n.loader import t
from app.keyboards.callbacks import MediaPersonCb
from app.keyboards.people import media_person_select_kb
from app.keyboards.wishes import wish_view_kb
from app.models.user import User
from app.services.person_service import get_person, get_user_people
from app.services.wish_service import WishLimitError, create_wish_with_media
from app.utils.bot_utils import BOT_MSG_KEY, get_message_text, reply_and_cleanup

router = Router(name="media")

_MEDIA_TYPE_NAMES = {
    "photo": {"ru": "Фото", "en": "Photo"},
    "video": {"ru": "Видео", "en": "Video"},
    "video_note": {"ru": "Кружок", "en": "Circle"},
    "document": {"ru": "Файл", "en": "File"},
    "location": {"ru": "Локация", "en": "Location"},
}


def _media_wish_text(
    media_type: str,
    lang: str,
    caption: str | None = None,
    filename: str | None = None,
    recorded_date: str | None = None,
) -> str:
    names = _MEDIA_TYPE_NAMES.get(media_type, {"ru": "Медиа", "en": "Media"})
    text = names.get(lang, names["en"])
    if caption:
        text += f" — {caption}"
    elif recorded_date:
        text += f" — {'записано' if lang == 'ru' else 'recorded'} {recorded_date}"
    elif filename:
        text += f" — {filename}"
    return text


@router.message(F.photo | F.video | F.video_note | F.document | F.location)
async def handle_media(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    media_filename = ""
    if message.photo:
        media_type = "photo"
    elif message.video:
        media_type = "video"
        media_filename = message.video.file_name or ""
    elif message.video_note:
        media_type = "video_note"
    elif message.document:
        media_type = "document"
        media_filename = message.document.file_name or ""
    elif message.location:
        media_type = "location"
    else:
        return

    media_recorded_date = ""
    if media_type in ("video_note", "location"):
        media_recorded_date = message.date.strftime("%d.%m.%Y")

    await state.update_data(
        media_chat_id=message.chat.id,
        media_message_id=message.message_id,
        media_type=media_type,
        media_caption=message.caption or "",
        media_filename=media_filename,
        media_recorded_date=media_recorded_date,
    )

    people = await get_user_people(session, user.id)

    if not people:
        await message.answer(t("media.no_people", lang))
        return

    await message.answer(
        t("media.choose_person", lang),
        reply_markup=media_person_select_kb(people, lang),
    )
    await state.set_state(MediaWishStates.waiting_person)


@router.callback_query(MediaWishStates.waiting_person, MediaPersonCb.filter(F.action == "select"))
async def media_person_selected(
    callback: CallbackQuery,
    callback_data: MediaPersonCb,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    person = await get_person(session, uuid.UUID(callback_data.id), user_id=user.id)
    if person is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    wish_text = _media_wish_text(
        data["media_type"],
        lang,
        data.get("media_caption"),
        filename=data.get("media_filename"),
        recorded_date=data.get("media_recorded_date"),
    )

    try:
        wish = await create_wish_with_media(
            session,
            user_id=user.id,
            text=wish_text,
            person_names=[person.name],
            chat_id=data["media_chat_id"],
            message_id=data["media_message_id"],
            media_type=data["media_type"],
        )
    except WishLimitError:
        from app.keyboards.subscription import upgrade_kb

        await callback.message.edit_text(  # type: ignore[union-attr]
            t("wishes.limit_reached", lang, max=str(user.max_wishes)),
            reply_markup=upgrade_kb(lang),
        )
        await state.clear()
        await callback.answer()
        return

    await state.clear()

    people_str = escape(person.name)
    card = (
        f"<b>{t('wishes.view_title', lang)}</b>\n\n"
        f"{escape(wish.text)}\n\n"
        f"{t('wishes.people_label', lang, people=people_str)}"
    )
    with contextlib.suppress(Exception):
        await callback.message.delete()  # type: ignore[union-attr]
    await callback.bot.send_message(  # type: ignore[union-attr]
        chat_id=data["media_chat_id"],
        text=card,
        reply_markup=wish_view_kb(wish, lang),
        reply_parameters=ReplyParameters(
            message_id=data["media_message_id"],
            allow_sending_without_reply=True,
        ),
    )
    await callback.answer()


@router.callback_query(MediaWishStates.waiting_person, MediaPersonCb.filter(F.action == "create"))
async def media_create_person(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("media.create_person_first", lang)
    )
    await state.update_data(**{BOT_MSG_KEY: callback.message.message_id})  # type: ignore[union-attr]
    await state.set_state(MediaWishStates.waiting_new_person_name)
    await callback.answer()


@router.message(MediaWishStates.waiting_new_person_name)
async def media_new_person_name(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    raw = await get_message_text(message, lang, user_id=user.id)
    if raw is None:
        return
    person_name = raw.strip()
    if not person_name:
        await reply_and_cleanup(message, state, t("errors.invalid_input", lang))
        return

    data = await state.get_data()
    bot_msg_id = data.get(BOT_MSG_KEY)
    wish_text = _media_wish_text(
        data["media_type"],
        lang,
        data.get("media_caption"),
        filename=data.get("media_filename"),
        recorded_date=data.get("media_recorded_date"),
    )

    try:
        wish = await create_wish_with_media(
            session,
            user_id=user.id,
            text=wish_text,
            person_names=[person_name],
            chat_id=data["media_chat_id"],
            message_id=data["media_message_id"],
            media_type=data["media_type"],
        )
    except WishLimitError:
        from app.keyboards.subscription import upgrade_kb

        await reply_and_cleanup(
            message,
            state,
            t("wishes.limit_reached", lang, max=str(user.max_wishes)),
            reply_markup=upgrade_kb(lang),
        )
        await state.clear()
        return

    await state.clear()

    if bot_msg_id:
        with contextlib.suppress(Exception):
            await message.bot.delete_message(message.chat.id, bot_msg_id)  # type: ignore[union-attr]
    with contextlib.suppress(Exception):
        await message.delete()

    people_str = escape(person_name)
    card = (
        f"<b>{t('wishes.view_title', lang)}</b>\n\n"
        f"{escape(wish.text)}\n\n"
        f"{t('wishes.people_label', lang, people=people_str)}"
    )
    await message.bot.send_message(  # type: ignore[union-attr]
        chat_id=data["media_chat_id"],
        text=card,
        reply_markup=wish_view_kb(wish, lang),
        reply_parameters=ReplyParameters(
            message_id=data["media_message_id"],
            allow_sending_without_reply=True,
        ),
    )


@router.callback_query(MediaWishStates.waiting_person, MediaPersonCb.filter(F.action == "cancel"))
async def media_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await state.clear()
    await callback.message.delete()  # type: ignore[union-attr]
    await callback.answer()
