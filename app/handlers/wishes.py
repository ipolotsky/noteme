import contextlib
import uuid
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyParameters
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import WishCreateStates, WishEditStates
from app.i18n.loader import t
from app.keyboards.callbacks import PageCb, WishCb, WishEditCb
from app.keyboards.main_menu import cancel_kb
from app.keyboards.wishes import (
    PAGE_SIZE,
    wish_delete_confirm_kb,
    wish_edit_kb,
    wish_skip_kb,
    wish_view_kb,
    wishes_list_kb,
)
from app.models.user import User
from app.schemas.wish import WishCreate, WishUpdate
from app.services.wish_service import (
    WishLimitError,
    count_user_wishes,
    create_wish,
    delete_wish,
    get_user_wishes,
    get_wish,
    update_wish,
)
from app.utils.bot_utils import BOT_MSG_KEY, get_message_text, reply_and_cleanup

router = Router(name="wishes")


async def show_wishes_list(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
    page: int = 0,
) -> None:
    total = await count_user_wishes(session, user.id)
    wishes = await get_user_wishes(session, user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE)

    text = t("wishes.empty", lang) if not wishes and total == 0 else t("wishes.title", lang)

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=wishes_list_kb(wishes, page, total, lang),
    )


@router.callback_query(WishCb.filter(F.action == "list"))
async def wish_list(
    callback: CallbackQuery,
    callback_data: WishCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_wishes_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


@router.callback_query(PageCb.filter(F.target == "wishes"))
async def wish_page(
    callback: CallbackQuery,
    callback_data: PageCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_wishes_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


@router.callback_query(WishCb.filter(F.action == "view"))
async def wish_view(
    callback: CallbackQuery,
    callback_data: WishCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    wish = await get_wish(session, uuid.UUID(callback_data.id), user_id=user.id)
    if wish is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    people_str = ", ".join(escape(tg.name) for tg in wish.people) if wish.people else t("wishes.no_people", lang)
    text = (
        f"<b>{t('wishes.view_title', lang)}</b>\n\n"
        f"{escape(wish.text)}\n\n"
        f"{t('wishes.people_label', lang, people=people_str)}"
    )

    if wish.media_link and not wish.media_link.is_deleted:
        with contextlib.suppress(Exception):
            await callback.message.delete()  # type: ignore[union-attr]
        await callback.bot.send_message(  # type: ignore[union-attr]
            chat_id=wish.media_link.chat_id,
            text=text,
            reply_markup=wish_view_kb(wish, lang),
            reply_parameters=ReplyParameters(
                message_id=wish.media_link.message_id,
                allow_sending_without_reply=True,
            ),
        )
    else:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=wish_view_kb(wish, lang),
        )
    await callback.answer()


@router.callback_query(WishCb.filter(F.action == "create"))
async def wish_create_start(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("wishes.create_text", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.update_data(**{BOT_MSG_KEY: callback.message.message_id})  # type: ignore[union-attr]
    await state.set_state(WishCreateStates.waiting_text)
    await callback.answer()


@router.message(WishCreateStates.waiting_text)
async def wish_create_text(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    text = await get_message_text(message, lang, user_id=user.id)
    if text is None:
        return
    await state.update_data(text=text)
    await reply_and_cleanup(
        message, state,
        t("wishes.create_people", lang),
        reply_markup=wish_skip_kb(lang),
    )
    await state.set_state(WishCreateStates.waiting_people)


@router.message(WishCreateStates.waiting_people)
async def wish_create_people(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    text = await get_message_text(message, lang, user_id=user.id)
    if text is None:
        return
    data = await state.get_data()
    person_names = [tg.strip() for tg in text.split(",") if tg.strip()]
    await _finish_wish_create(message, state, user, lang, session, data, person_names)


@router.callback_query(WishCreateStates.waiting_people, F.data == "skip")
async def wish_create_skip_people(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    await _finish_wish_create(callback.message, state, user, lang, session, data, [])  # type: ignore[arg-type]
    await callback.answer()


async def _finish_wish_create(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
    data: dict,
    person_names: list[str],
) -> None:
    wish_data = WishCreate(
        text=data["text"],
        person_names=person_names or [],
    )

    try:
        wish = await create_wish(session, user.id, wish_data)
    except WishLimitError:
        from app.keyboards.subscription import upgrade_kb

        await reply_and_cleanup(
            message, state,
            t("wishes.limit_reached", lang, max=str(user.max_wishes)),
            reply_markup=upgrade_kb(lang),
        )
        await state.clear()
        return

    await reply_and_cleanup(
        message, state,
        t("wishes.created", lang),
        reply_markup=wish_view_kb(wish, lang),
    )
    await state.clear()


@router.callback_query(WishCb.filter(F.action == "edit"))
async def wish_edit_start(
    callback: CallbackQuery,
    callback_data: WishCb,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("wishes.edit", lang),
        reply_markup=wish_edit_kb(callback_data.id, lang),
    )
    await callback.answer()


@router.callback_query(WishEditCb.filter(F.field == "text"))
async def wish_edit_text_start(
    callback: CallbackQuery,
    callback_data: WishEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_wish_id=callback_data.id, **{BOT_MSG_KEY: callback.message.message_id})  # type: ignore[union-attr]
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("wishes.create_text", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(WishEditStates.waiting_text)
    await callback.answer()


@router.message(WishEditStates.waiting_text)
async def wish_edit_text(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    text = await get_message_text(message, lang, user_id=user.id)
    if text is None:
        return
    data = await state.get_data()
    wish = await update_wish(
        session, uuid.UUID(data["edit_wish_id"]), WishUpdate(text=text),
        user_id=user.id,
    )
    if wish:
        await reply_and_cleanup(
            message, state,
            t("wishes.updated", lang),
            reply_markup=wish_view_kb(wish, lang),
        )
    else:
        await reply_and_cleanup(message, state, t("errors.not_found", lang))
    await state.clear()


@router.callback_query(WishEditCb.filter(F.field == "people"))
async def wish_edit_people_start(
    callback: CallbackQuery,
    callback_data: WishEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_wish_id=callback_data.id, **{BOT_MSG_KEY: callback.message.message_id})  # type: ignore[union-attr]
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("wishes.create_people", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(WishEditStates.waiting_people)
    await callback.answer()


@router.message(WishEditStates.waiting_people)
async def wish_edit_people(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    text = await get_message_text(message, lang, user_id=user.id)
    if text is None:
        return
    data = await state.get_data()
    person_names = [tg.strip() for tg in text.split(",") if tg.strip()]
    wish = await update_wish(
        session, uuid.UUID(data["edit_wish_id"]), WishUpdate(person_names=person_names),
        user_id=user.id,
    )
    if wish:
        await reply_and_cleanup(
            message, state,
            t("wishes.updated", lang),
            reply_markup=wish_view_kb(wish, lang),
        )
    else:
        await reply_and_cleanup(message, state, t("errors.not_found", lang))
    await state.clear()


@router.callback_query(WishCb.filter(F.action == "delete"))
async def wish_delete_ask(
    callback: CallbackQuery,
    callback_data: WishCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    wish = await get_wish(session, uuid.UUID(callback_data.id), user_id=user.id)
    if wish is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("wishes.delete_confirm", lang),
        reply_markup=wish_delete_confirm_kb(callback_data.id, lang),
    )
    await callback.answer()


@router.callback_query(WishCb.filter(F.action == "confirm_delete"))
async def wish_delete_confirm(
    callback: CallbackQuery,
    callback_data: WishCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await delete_wish(session, uuid.UUID(callback_data.id), user_id=user.id)
    await callback.answer(t("wishes.deleted", lang))
    await show_wishes_list(callback, user, lang, session)
