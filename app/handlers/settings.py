"""Settings handler — language, timezone, notifications, spoiler."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import SettingsStates
from app.i18n.loader import t
from app.keyboards.callbacks import LangCb, SettingsCb
from app.keyboards.main_menu import cancel_kb
from app.keyboards.settings import language_select_kb, settings_kb
from app.models.user import User
from app.schemas.user import UserUpdate
from app.services.user_service import update_user

router = Router(name="settings")


# --- Shared display helper ---


async def show_settings(
    callback: CallbackQuery,
    user: User,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("settings.title", lang),
        reply_markup=settings_kb(user, lang),
    )


# --- View ---


@router.callback_query(SettingsCb.filter(F.action == "view"))
async def settings_view(
    callback: CallbackQuery,
    user: User,
    lang: str,
) -> None:
    await show_settings(callback, user, lang)
    await callback.answer()


# --- Language ---


@router.callback_query(SettingsCb.filter(F.action == "language"))
async def settings_language(
    callback: CallbackQuery,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("choose_language", lang),
        reply_markup=language_select_kb(back_lang=lang),
    )
    await callback.answer()


@router.callback_query(LangCb.filter())
async def settings_set_language(
    callback: CallbackQuery,
    callback_data: LangCb,
    user: User,
    session: AsyncSession,
) -> None:
    new_lang = callback_data.code
    await update_user(session, user.id, UserUpdate(language=new_lang))
    user.language = new_lang  # Update in-memory for immediate UI refresh

    await callback.answer(t("language_set", new_lang))
    await show_settings(callback, user, new_lang)


# --- Timezone ---


@router.callback_query(SettingsCb.filter(F.action == "timezone"))
async def settings_timezone(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("settings.change_timezone", lang) + "\n\nExamples: Europe/Moscow, US/Eastern, Asia/Tokyo",
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(SettingsStates.waiting_timezone)
    await callback.answer()


@router.message(SettingsStates.waiting_timezone)
async def settings_set_timezone(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    tz = (message.text or "").strip()
    if not tz or "/" not in tz:
        await message.answer(t("errors.invalid_input", lang))
        return

    await update_user(session, user.id, UserUpdate(timezone=tz))
    user.timezone = tz
    await state.clear()
    await message.answer(
        t("settings.saved", lang),
        reply_markup=settings_kb(user, lang),
    )


# --- Notifications toggle ---


@router.callback_query(SettingsCb.filter(F.action == "notif_toggle"))
async def settings_notif_toggle(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    new_val = not user.notifications_enabled
    await update_user(session, user.id, UserUpdate(notifications_enabled=new_val))
    user.notifications_enabled = new_val

    await callback.answer(t("settings.saved", lang))
    await show_settings(callback, user, lang)


# --- Notification time ---


@router.callback_query(SettingsCb.filter(F.action == "notif_time"))
async def settings_notif_time(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    text = t("settings.change_notification_time", lang) + "\n\nFormat: HH:MM (e.g. 09:00, 21:30)"
    try:
        tz = ZoneInfo(user.timezone)
        now = datetime.now(tz).strftime("%H:%M")
        text += f"\n\n{t('settings.current_time', lang, time=now)}"
    except Exception:
        pass
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(SettingsStates.waiting_notification_time)
    await callback.answer()


@router.message(SettingsStates.waiting_notification_time)
async def settings_set_notif_time(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    try:
        parts = (message.text or "").strip().split(":")
        new_time = time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        await message.answer(t("errors.invalid_input", lang))
        return

    await update_user(session, user.id, UserUpdate(notification_time=new_time))
    user.notification_time = new_time
    await state.clear()
    await message.answer(
        t("settings.saved", lang),
        reply_markup=settings_kb(user, lang),
    )


# --- Notification count ---


@router.callback_query(SettingsCb.filter(F.action == "notif_count"))
async def settings_notif_count(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("settings.change_notification_count", lang) + "\n\n1-10",
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(SettingsStates.waiting_notification_count)
    await callback.answer()


@router.message(SettingsStates.waiting_notification_count)
async def settings_set_notif_count(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    try:
        count = int((message.text or "").strip())
        if not 1 <= count <= 10:
            raise ValueError
    except ValueError:
        await message.answer(t("errors.invalid_input", lang))
        return

    await update_user(session, user.id, UserUpdate(notification_count=count))
    user.notification_count = count
    await state.clear()
    await message.answer(
        t("settings.saved", lang),
        reply_markup=settings_kb(user, lang),
    )


# --- Spoiler toggle ---


@router.callback_query(SettingsCb.filter(F.action == "spoiler"))
async def settings_spoiler_toggle(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    new_val = not user.spoiler_enabled
    await update_user(session, user.id, UserUpdate(spoiler_enabled=new_val))
    user.spoiler_enabled = new_val

    await callback.answer(t("settings.saved", lang))
    await show_settings(callback, user, lang)
