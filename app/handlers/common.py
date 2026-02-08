"""Main menu handler — navigation hub + cancel."""

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


# --- Cancel (universal escape from any FSM state) ---


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


# --- Main menu ---


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


@router.callback_query(MenuCb.filter(F.action == "notes"))
async def menu_notes(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.handlers.notes import show_notes_list
    await show_notes_list(callback, user, lang, session, page=0)
    await callback.answer()


@router.callback_query(MenuCb.filter(F.action == "tags"))
async def menu_tags(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.handlers.tags import show_tags_list
    await show_tags_list(callback, user, lang, session, page=0)
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
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.handlers.feed import show_feed_list
    await show_feed_list(callback, user, lang, session, page=0)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    await callback.answer()
