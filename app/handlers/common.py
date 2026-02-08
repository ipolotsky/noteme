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

# Emoji prefixes for persistent reply keyboard button matching
_EMOJI_FEED = "\U0001f4c5"      # 📅
_EMOJI_EVENTS = "\U0001f4cb"    # 📋
_EMOJI_NOTES = "\U0001f4dd"     # 📝
_EMOJI_TAGS = "\U0001f3f7"      # 🏷
_EMOJI_SETTINGS = "\u2699"      # ⚙


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


# --- Persistent reply keyboard button handlers ---
# These match text messages sent when user presses the reply keyboard buttons.


def _is_reply_menu_button(text: str | None) -> bool:
    """Check if message text matches a persistent keyboard button."""
    if not text:
        return False
    return text.startswith((_EMOJI_FEED, _EMOJI_EVENTS, _EMOJI_NOTES, _EMOJI_TAGS, _EMOJI_SETTINGS))


@router.message(F.text.startswith(_EMOJI_FEED))
async def reply_kb_feed(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()
    from app.keyboards.feed import PAGE_SIZE, feed_list_kb
    from app.services.beautiful_date_service import count_user_feed, get_user_feed

    total = await count_user_feed(session, user.id)
    items = await get_user_feed(session, user.id, offset=0, limit=PAGE_SIZE)

    if not items:
        await message.answer(t("feed.empty", lang), reply_markup=main_menu_kb(lang))
    else:
        await message.answer(t("feed.title", lang), reply_markup=feed_list_kb(items, 0, total, lang))


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


@router.message(F.text.startswith(_EMOJI_NOTES))
async def reply_kb_notes(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()
    from app.keyboards.notes import PAGE_SIZE, notes_list_kb
    from app.services.note_service import count_user_notes, get_user_notes

    total = await count_user_notes(session, user.id)
    notes = await get_user_notes(session, user.id, offset=0, limit=PAGE_SIZE)
    text = t("notes.empty", lang) if not notes and total == 0 else t("notes.title", lang)
    await message.answer(text, reply_markup=notes_list_kb(notes, 0, total, lang))


@router.message(F.text.startswith(_EMOJI_TAGS))
async def reply_kb_tags(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()
    from app.keyboards.tags import PAGE_SIZE, tags_list_kb
    from app.services.tag_service import get_user_tags

    all_tags = await get_user_tags(session, user.id)
    total = len(all_tags)
    tags = all_tags[:PAGE_SIZE]
    text = t("tags.empty", lang) if not tags and total == 0 else t("tags.title", lang)
    await message.answer(text, reply_markup=tags_list_kb(tags, 0, total, lang))


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
