from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.i18n.loader import t
from app.keyboards.callbacks import MenuCb
from app.keyboards.main_menu import main_menu_kb
from app.models.user import User

router = Router(name="common")

_EMOJI_FEED = "\U0001f4c5"
_EMOJI_EVENTS = "\U0001f4cb"
_EMOJI_WISHES = "\U0001f381"
_EMOJI_PEOPLE = "\U0001f464"
_EMOJI_SETTINGS = "\u2699"


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    current = await state.get_state()
    await state.clear()
    if current is None:
        await message.answer(
            f"\U0001f3e0 {user.first_name}",
            reply_markup=main_menu_kb(lang),
        )
    else:
        await message.answer(
            f"\u2716 {t('menu.cancel', lang)}\n\n\U0001f3e0 {user.first_name}",
            reply_markup=main_menu_kb(lang),
        )


@router.callback_query(F.data == "cancel")
async def cancel_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"\U0001f3e0 {user.first_name}",
        reply_markup=main_menu_kb(lang),
    )
    await callback.answer()


@router.callback_query(MenuCb.filter(F.action == "main"))
async def show_main_menu(
    callback: CallbackQuery,
    user: User,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"\U0001f3e0 {user.first_name}",
        reply_markup=main_menu_kb(lang),
    )
    await callback.answer()


@router.callback_query(MenuCb.filter(F.action == "events"))
async def menu_events(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.handlers.events import show_events_list
    await show_events_list(callback, user, lang, session, page=0)
    await callback.answer()


@router.callback_query(MenuCb.filter(F.action == "wishes"))
async def menu_wishes(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.handlers.wishes import show_wishes_list
    await show_wishes_list(callback, user, lang, session, page=0)
    await callback.answer()


@router.callback_query(MenuCb.filter(F.action == "people"))
async def menu_people(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.handlers.people import show_people_list
    await show_people_list(callback, user, lang, session, page=0)
    await callback.answer()


@router.callback_query(MenuCb.filter(F.action == "settings"))
async def menu_settings(
    callback: CallbackQuery,
    user: User,
    lang: str,
) -> None:
    from app.handlers.settings import show_settings
    await show_settings(callback, user, lang)
    await callback.answer()


@router.callback_query(MenuCb.filter(F.action == "feed"))
async def menu_feed(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.handlers.feed import show_feed_list
    await show_feed_list(callback, user, lang, session, state, page=0)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    await callback.answer()


def _is_reply_menu_button(text: str | None) -> bool:
    if not text:
        return False
    return text.startswith((_EMOJI_FEED, _EMOJI_EVENTS, _EMOJI_WISHES, _EMOJI_PEOPLE, _EMOJI_SETTINGS))


@router.message(F.text.startswith(_EMOJI_FEED))
async def reply_kb_feed(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()
    from app.handlers.feed import send_feed_messages

    await send_feed_messages(message, user, lang, session, state, page=0)


@router.message(F.text.startswith(_EMOJI_EVENTS))
async def reply_kb_events(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()
    from app.keyboards.events import PAGE_SIZE, events_list_kb
    from app.services.event_service import count_user_events, get_user_events

    total = await count_user_events(session, user.id)
    events = await get_user_events(session, user.id, offset=0, limit=PAGE_SIZE)
    text = t("events.empty", lang) if not events and total == 0 else t("events.title", lang)
    await message.answer(text, reply_markup=events_list_kb(events, 0, total, lang))


@router.message(F.text.startswith(_EMOJI_WISHES))
async def reply_kb_wishes(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()
    from app.keyboards.wishes import PAGE_SIZE, wishes_list_kb
    from app.services.wish_service import count_user_wishes, get_user_wishes

    total = await count_user_wishes(session, user.id)
    wishes = await get_user_wishes(session, user.id, offset=0, limit=PAGE_SIZE)
    text = t("wishes.empty", lang) if not wishes and total == 0 else t("wishes.title", lang)
    await message.answer(text, reply_markup=wishes_list_kb(wishes, 0, total, lang))


@router.message(F.text.startswith(_EMOJI_PEOPLE))
async def reply_kb_people(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()
    from app.keyboards.people import PAGE_SIZE, people_list_kb
    from app.services.person_service import get_user_people

    all_people = await get_user_people(session, user.id)
    total = len(all_people)
    people = all_people[:PAGE_SIZE]
    text = t("people.empty", lang) if not people and total == 0 else t("people.title", lang)
    await message.answer(text, reply_markup=people_list_kb(people, 0, total, lang))


@router.message(F.text.startswith(_EMOJI_SETTINGS))
async def reply_kb_settings(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    await state.clear()
    from app.keyboards.settings import settings_kb

    await message.answer(t("settings.title", lang), reply_markup=settings_kb(user, lang))
