"""Event handlers — list, view, create, edit, delete."""

import uuid
from datetime import datetime
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import EventCreateStates, EventEditStates
from app.i18n.loader import t
from app.keyboards.callbacks import EventCb, EventEditCb, PageCb
from app.keyboards.events import (
    PAGE_SIZE,
    event_delete_confirm_kb,
    event_edit_kb,
    event_skip_kb,
    event_view_kb,
    events_list_kb,
)
from app.keyboards.main_menu import cancel_kb
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate
from app.services.event_service import (
    EventLimitError,
    count_user_events,
    create_event,
    delete_event,
    get_event,
    get_user_events,
    update_event,
)

router = Router(name="events")


# --- Shared display helpers ---


async def show_events_list(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
    page: int = 0,
) -> None:
    total = await count_user_events(session, user.id)
    events = await get_user_events(session, user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE)

    text = t("events.empty", lang) if not events and total == 0 else t("events.title", lang)

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=events_list_kb(events, page, total, lang),
    )


# --- List ---


@router.callback_query(EventCb.filter(F.action == "list"))
async def event_list(
    callback: CallbackQuery,
    callback_data: EventCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_events_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


@router.callback_query(PageCb.filter(F.target == "events"))
async def event_page(
    callback: CallbackQuery,
    callback_data: PageCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_events_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


# --- View ---


@router.callback_query(EventCb.filter(F.action == "view"))
async def event_view(
    callback: CallbackQuery,
    callback_data: EventCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    event = await get_event(session, uuid.UUID(callback_data.id), user_id=user.id)
    if event is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    tags_str = ", ".join(escape(tg.name) for tg in event.tags) if event.tags else t("events.no_tags", lang)
    text = (
        f"<b>{t('events.view_title', lang, title=escape(event.title))}</b>\n"
        f"{t('events.date_label', lang, date=event.event_date.strftime('%d.%m.%Y'))}\n"
        f"{t('events.tags_label', lang, tags=tags_str)}"
    )
    if event.description:
        text += f"\n\n{escape(event.description)}"

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=event_view_kb(event, lang),
    )
    await callback.answer()


# --- Create ---


@router.callback_query(EventCb.filter(F.action == "create"))
async def event_create_start(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.create_title", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(EventCreateStates.waiting_title)
    await callback.answer()


@router.message(EventCreateStates.waiting_title)
async def event_create_title(
    message: Message,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(title=message.text)
    await message.answer(
        t("events.create_date", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(EventCreateStates.waiting_date)


@router.message(EventCreateStates.waiting_date)
async def event_create_date(
    message: Message,
    state: FSMContext,
    lang: str,
) -> None:
    try:
        event_date = datetime.strptime(message.text or "", "%d.%m.%Y").date()
    except ValueError:
        await message.answer(t("events.invalid_date", lang))
        return

    await state.update_data(event_date=event_date.isoformat())
    await message.answer(
        t("events.create_description", lang),
        reply_markup=event_skip_kb(lang),
    )
    await state.set_state(EventCreateStates.waiting_description)


@router.message(EventCreateStates.waiting_description)
async def event_create_description(
    message: Message,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(description=message.text)
    await message.answer(
        t("events.create_tags", lang),
        reply_markup=event_skip_kb(lang),
    )
    await state.set_state(EventCreateStates.waiting_tags)


@router.callback_query(EventCreateStates.waiting_description, F.data == "skip")
async def event_create_skip_description(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.create_tags", lang),
        reply_markup=event_skip_kb(lang),
    )
    await state.set_state(EventCreateStates.waiting_tags)
    await callback.answer()


@router.message(EventCreateStates.waiting_tags)
async def event_create_tags(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    tag_names = [tg.strip() for tg in (message.text or "").split(",") if tg.strip()]
    await _finish_event_create(message, state, user, lang, session, data, tag_names)


@router.callback_query(EventCreateStates.waiting_tags, F.data == "skip")
async def event_create_skip_tags(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    await _finish_event_create(callback.message, state, user, lang, session, data, [])  # type: ignore[arg-type]
    await callback.answer()


async def _finish_event_create(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
    data: dict,
    tag_names: list[str],
) -> None:
    from datetime import date as date_type

    event_date = date_type.fromisoformat(data["event_date"])
    event_data = EventCreate(
        title=data["title"],
        event_date=event_date,
        description=data.get("description"),
        tag_names=tag_names or [],
    )

    try:
        event = await create_event(session, user.id, event_data)
    except EventLimitError:
        await message.answer(t("events.limit_reached", lang, max=str(user.max_events)))
        await state.clear()
        return

    from app.services.beautiful_dates.engine import recalculate_for_event
    await recalculate_for_event(session, event)

    await state.clear()
    await message.answer(
        t("events.created", lang, title=escape(event.title)),
        reply_markup=event_view_kb(event, lang),
    )


# --- Edit ---


@router.callback_query(EventCb.filter(F.action == "edit"))
async def event_edit_start(
    callback: CallbackQuery,
    callback_data: EventCb,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.edit", lang),
        reply_markup=event_edit_kb(callback_data.id, lang),
    )
    await callback.answer()


@router.callback_query(EventEditCb.filter(F.field == "title"))
async def event_edit_title_start(
    callback: CallbackQuery,
    callback_data: EventEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_event_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.create_title", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(EventEditStates.waiting_title)
    await callback.answer()


@router.message(EventEditStates.waiting_title)
async def event_edit_title(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    event = await update_event(
        session, uuid.UUID(data["edit_event_id"]), EventUpdate(title=message.text),
        user_id=user.id,
    )
    await state.clear()
    if event:
        await message.answer(
            t("events.updated", lang),
            reply_markup=event_view_kb(event, lang),
        )
    else:
        await message.answer(t("errors.not_found", lang))


@router.callback_query(EventEditCb.filter(F.field == "date"))
async def event_edit_date_start(
    callback: CallbackQuery,
    callback_data: EventEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_event_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.create_date", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(EventEditStates.waiting_date)
    await callback.answer()


@router.message(EventEditStates.waiting_date)
async def event_edit_date(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    try:
        event_date = datetime.strptime(message.text or "", "%d.%m.%Y").date()
    except ValueError:
        await message.answer(t("events.invalid_date", lang))
        return

    data = await state.get_data()
    event = await update_event(
        session, uuid.UUID(data["edit_event_id"]), EventUpdate(event_date=event_date),
        user_id=user.id,
    )
    if event:
        from app.services.beautiful_dates.engine import recalculate_for_event
        await recalculate_for_event(session, event)

    await state.clear()
    if event:
        await message.answer(
            t("events.updated", lang),
            reply_markup=event_view_kb(event, lang),
        )
    else:
        await message.answer(t("errors.not_found", lang))


@router.callback_query(EventEditCb.filter(F.field == "description"))
async def event_edit_desc_start(
    callback: CallbackQuery,
    callback_data: EventEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_event_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.create_description", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(EventEditStates.waiting_description)
    await callback.answer()


@router.message(EventEditStates.waiting_description)
async def event_edit_desc(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    event = await update_event(
        session, uuid.UUID(data["edit_event_id"]), EventUpdate(description=message.text),
        user_id=user.id,
    )
    await state.clear()
    if event:
        await message.answer(
            t("events.updated", lang),
            reply_markup=event_view_kb(event, lang),
        )
    else:
        await message.answer(t("errors.not_found", lang))


@router.callback_query(EventEditCb.filter(F.field == "tags"))
async def event_edit_tags_start(
    callback: CallbackQuery,
    callback_data: EventEditCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(edit_event_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.create_tags", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(EventEditStates.waiting_tags)
    await callback.answer()


@router.message(EventEditStates.waiting_tags)
async def event_edit_tags(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    tag_names = [tg.strip() for tg in (message.text or "").split(",") if tg.strip()]
    event = await update_event(
        session, uuid.UUID(data["edit_event_id"]), EventUpdate(tag_names=tag_names),
        user_id=user.id,
    )
    await state.clear()
    if event:
        await message.answer(
            t("events.updated", lang),
            reply_markup=event_view_kb(event, lang),
        )
    else:
        await message.answer(t("errors.not_found", lang))


# --- Delete ---


@router.callback_query(EventCb.filter(F.action == "delete"))
async def event_delete_ask(
    callback: CallbackQuery,
    callback_data: EventCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    event = await get_event(session, uuid.UUID(callback_data.id), user_id=user.id)
    if event is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    if event.is_system:
        await callback.answer(
            t("events.cannot_delete_system", lang), show_alert=True
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.delete_confirm", lang, title=escape(event.title)),
        reply_markup=event_delete_confirm_kb(callback_data.id, lang),
    )
    await callback.answer()


@router.callback_query(EventCb.filter(F.action == "confirm_delete"))
async def event_delete_confirm(
    callback: CallbackQuery,
    callback_data: EventCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    deleted = await delete_event(session, uuid.UUID(callback_data.id), user_id=user.id)
    if deleted:
        await callback.answer(t("events.deleted", lang))
    else:
        await callback.answer(t("events.cannot_delete_system", lang), show_alert=True)

    # Show events list
    await show_events_list(callback, user, lang, session)


# --- Beautiful dates for event ---


@router.callback_query(EventCb.filter(F.action == "dates"))
async def event_dates(
    callback: CallbackQuery,
    callback_data: EventCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.services.beautiful_date_service import get_event_beautiful_dates
    from app.utils.date_utils import format_relative_date

    event = await get_event(session, uuid.UUID(callback_data.id), user_id=user.id)
    if event is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    dates = await get_event_beautiful_dates(session, event.id, limit=10)
    if not dates:
        await callback.answer(t("feed.empty", lang), show_alert=True)
        return

    text = f"\U0001f52e <b>{t('events.beautiful_dates', lang)}: {escape(event.title)}</b>\n\n"
    for bd in dates:
        label = bd.label_ru if lang == "ru" else bd.label_en
        relative = format_relative_date(bd.target_date, lang)
        text += f"\U0001f538 {relative} — {label}\n"
        text += f"    {bd.target_date.strftime('%d.%m.%Y')}\n\n"

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=EventCb(action="view", id=callback_data.id).pack(),
        )],
    ])

    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()
