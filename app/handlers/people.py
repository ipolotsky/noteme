import uuid
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import PersonCreateStates, PersonRenameStates
from app.i18n.loader import t
from app.keyboards.callbacks import EventCb, PageCb, PersonCb, WishCb
from app.keyboards.main_menu import cancel_kb
from app.keyboards.people import (
    PAGE_SIZE,
    people_list_kb,
    person_delete_confirm_kb,
    person_view_kb,
)
from app.models.event import EventPerson
from app.models.user import User
from app.models.wish import WishPerson
from app.services.event_service import get_events_by_person_names
from app.services.person_service import (
    create_person,
    delete_person,
    get_person,
    get_user_people,
    rename_person,
)
from app.services.wish_service import get_wishes_by_person_names

router = Router(name="people")


async def show_people_list(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
    page: int = 0,
) -> None:
    all_people = await get_user_people(session, user.id)
    total = len(all_people)
    start = page * PAGE_SIZE
    people = all_people[start : start + PAGE_SIZE]

    text = t("people.empty", lang) if not people and total == 0 else t("people.title", lang)

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=people_list_kb(people, page, total, lang),
    )


@router.callback_query(PersonCb.filter(F.action == "list"))
async def person_list(
    callback: CallbackQuery,
    callback_data: PersonCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_people_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


@router.callback_query(PageCb.filter(F.target == "people"))
async def person_page(
    callback: CallbackQuery,
    callback_data: PageCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await show_people_list(callback, user, lang, session, page=callback_data.page)
    await callback.answer()


@router.callback_query(PersonCb.filter(F.action == "view"))
async def person_view(
    callback: CallbackQuery,
    callback_data: PersonCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    person = await get_person(session, uuid.UUID(callback_data.id), user_id=user.id)
    if person is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    events_count = (await session.execute(
        select(func.count()).where(EventPerson.person_id == person.id)
    )).scalar_one()
    wishes_count = (await session.execute(
        select(func.count()).where(WishPerson.person_id == person.id)
    )).scalar_one()

    text = (
        f"<b>\U0001f464 {escape(person.name)}</b>\n\n"
        f"{t('people.events_count', lang, count=str(events_count))}\n"
        f"{t('people.wishes_count', lang, count=str(wishes_count))}"
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=person_view_kb(person, lang, events_count=events_count, wishes_count=wishes_count),
    )
    await callback.answer()


@router.callback_query(PersonCb.filter(F.action == "events"))
async def person_events(
    callback: CallbackQuery,
    callback_data: PersonCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    person = await get_person(session, uuid.UUID(callback_data.id), user_id=user.id)
    if person is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    events = await get_events_by_person_names(session, user.id, [person.name], limit=20)

    text = f"<b>\U0001f464 {escape(person.name)} — {t('people.show_events', lang)}</b>\n\n"
    if not events:
        text += t("events.empty", lang)
    else:
        for ev in events:
            text += f"\U0001f4c5 <b>{escape(ev.title)}</b> — {ev.event_date.strftime('%d.%m.%Y')}\n"

    rows: list[list[InlineKeyboardButton]] = []
    for ev in events:
        rows.append([InlineKeyboardButton(
            text=f"\U0001f4c5 {ev.title}",
            callback_data=EventCb(action="view", id=str(ev.id)).pack(),
        )])
    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=PersonCb(action="view", id=callback_data.id).pack(),
    )])

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(PersonCb.filter(F.action == "wishes"))
async def person_wishes(
    callback: CallbackQuery,
    callback_data: PersonCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    person = await get_person(session, uuid.UUID(callback_data.id), user_id=user.id)
    if person is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    wishes = await get_wishes_by_person_names(session, user.id, [person.name], limit=20)

    text = f"<b>\U0001f464 {escape(person.name)} — {t('people.show_wishes', lang)}</b>\n\n"
    if not wishes:
        text += t("wishes.empty", lang)
    else:
        for nt in wishes:
            preview = escape(nt.text[:50]) + ("..." if len(nt.text) > 50 else "")
            text += f"\U0001f4dd {preview}\n"

    rows: list[list[InlineKeyboardButton]] = []
    for nt in wishes:
        preview = nt.text[:40] + ("..." if len(nt.text) > 40 else "")
        rows.append([InlineKeyboardButton(
            text=f"\U0001f4dd {preview}",
            callback_data=WishCb(action="view", id=str(nt.id)).pack(),
        )])
    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=PersonCb(action="view", id=callback_data.id).pack(),
    )])

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(PersonCb.filter(F.action == "create"))
async def person_create_start(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("people.create_name", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(PersonCreateStates.waiting_name)
    await callback.answer()


@router.message(PersonCreateStates.waiting_name)
async def person_create_name(
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

    person = await create_person(session, user.id, name)
    await state.clear()
    await message.answer(
        t("people.created", lang, name=escape(person.name)),
        reply_markup=person_view_kb(person, lang),
    )


@router.callback_query(PersonCb.filter(F.action == "rename"))
async def person_rename_start(
    callback: CallbackQuery,
    callback_data: PersonCb,
    state: FSMContext,
    lang: str,
) -> None:
    await state.update_data(rename_person_id=callback_data.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("people.rename_prompt", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(PersonRenameStates.waiting_name)
    await callback.answer()


@router.message(PersonRenameStates.waiting_name)
async def person_rename_name(
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

    person = await rename_person(
        session, uuid.UUID(data["rename_person_id"]), new_name, user_id=user.id
    )
    await state.clear()

    if person is None:
        from app.keyboards.main_menu import main_menu_kb
        await message.answer(
            t("people.already_exists", lang, name=escape(new_name)),
            reply_markup=main_menu_kb(lang),
        )
        return

    await message.answer(
        t("people.renamed", lang, name=escape(person.name)),
        reply_markup=person_view_kb(person, lang),
    )


@router.callback_query(PersonCb.filter(F.action == "delete"))
async def person_delete_ask(
    callback: CallbackQuery,
    callback_data: PersonCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    person = await get_person(session, uuid.UUID(callback_data.id), user_id=user.id)
    if person is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("people.delete_confirm", lang, name=escape(person.name)),
        reply_markup=person_delete_confirm_kb(callback_data.id, lang),
    )
    await callback.answer()


@router.callback_query(PersonCb.filter(F.action == "confirm_delete"))
async def person_delete_confirm(
    callback: CallbackQuery,
    callback_data: PersonCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await delete_person(session, uuid.UUID(callback_data.id), user_id=user.id)
    await callback.answer(t("people.deleted", lang))
    await show_people_list(callback, user, lang, session)
