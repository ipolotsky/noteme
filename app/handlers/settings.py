from datetime import datetime, time
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import SettingsStates
from app.i18n.loader import t
from app.keyboards.callbacks import LangCb, SettingsCb
from app.keyboards.main_menu import cancel_kb, persistent_menu_kb
from app.keyboards.settings import (
    digest_day_select_kb,
    language_select_kb,
    notification_settings_kb,
    settings_kb,
)
from app.models.user import User
from app.schemas.user import UserUpdate
from app.services.user_service import update_user

router = Router(name="settings")


async def show_settings(
    callback: CallbackQuery,
    user: User,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("settings.title", lang),
        reply_markup=settings_kb(user, lang),
    )


async def show_notification_settings(
    callback: CallbackQuery,
    user: User,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("settings.notification_submenu", lang),
        reply_markup=notification_settings_kb(user, lang),
    )


@router.callback_query(SettingsCb.filter(F.action == "view"))
async def settings_view(
    callback: CallbackQuery,
    user: User,
    lang: str,
) -> None:
    await show_settings(callback, user, lang)
    await callback.answer()


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
    user.language = new_lang

    await callback.answer(t("language_set", new_lang))
    await show_settings(callback, user, new_lang)
    await callback.message.answer(  # type: ignore[union-attr]
        t("language_set", new_lang),
        reply_markup=persistent_menu_kb(new_lang),
    )


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


@router.callback_query(SettingsCb.filter(F.action == "notif_submenu"))
async def settings_notif_submenu(
    callback: CallbackQuery,
    user: User,
    lang: str,
) -> None:
    await show_notification_settings(callback, user, lang)
    await callback.answer()


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
    await show_notification_settings(callback, user, lang)


@router.callback_query(SettingsCb.filter(F.action == "day_before_toggle"))
async def settings_day_before_toggle(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    new_val = not user.notify_day_before
    await update_user(session, user.id, UserUpdate(notify_day_before=new_val))
    user.notify_day_before = new_val

    await callback.answer(t("settings.saved", lang))
    await show_notification_settings(callback, user, lang)


@router.callback_query(SettingsCb.filter(F.action == "day_before_time"))
async def settings_day_before_time(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    text = t("settings.change_time", lang)
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
    await state.set_state(SettingsStates.waiting_day_before_time)
    await callback.answer()


@router.message(SettingsStates.waiting_day_before_time)
async def settings_set_day_before_time(
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

    await update_user(session, user.id, UserUpdate(notify_day_before_time=new_time))
    user.notify_day_before_time = new_time
    await state.clear()
    await message.answer(
        t("settings.saved", lang),
        reply_markup=notification_settings_kb(user, lang),
    )


@router.callback_query(SettingsCb.filter(F.action == "week_before_toggle"))
async def settings_week_before_toggle(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    new_val = not user.notify_week_before
    await update_user(session, user.id, UserUpdate(notify_week_before=new_val))
    user.notify_week_before = new_val

    await callback.answer(t("settings.saved", lang))
    await show_notification_settings(callback, user, lang)


@router.callback_query(SettingsCb.filter(F.action == "week_before_time"))
async def settings_week_before_time(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    text = t("settings.change_time", lang)
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
    await state.set_state(SettingsStates.waiting_week_before_time)
    await callback.answer()


@router.message(SettingsStates.waiting_week_before_time)
async def settings_set_week_before_time(
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

    await update_user(session, user.id, UserUpdate(notify_week_before_time=new_time))
    user.notify_week_before_time = new_time
    await state.clear()
    await message.answer(
        t("settings.saved", lang),
        reply_markup=notification_settings_kb(user, lang),
    )


@router.callback_query(SettingsCb.filter(F.action == "digest_toggle"))
async def settings_digest_toggle(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    new_val = not user.notify_weekly_digest
    await update_user(session, user.id, UserUpdate(notify_weekly_digest=new_val))
    user.notify_weekly_digest = new_val

    await callback.answer(t("settings.saved", lang))
    await show_notification_settings(callback, user, lang)


@router.callback_query(SettingsCb.filter(F.action == "digest_day"))
async def settings_digest_day(
    callback: CallbackQuery,
    lang: str,
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("settings.choose_digest_day", lang),
        reply_markup=digest_day_select_kb(lang),
    )
    await callback.answer()


@router.callback_query(SettingsCb.filter(F.action == "set_digest_day"))
async def settings_set_digest_day(
    callback: CallbackQuery,
    callback_data: SettingsCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    day = int(callback_data.value)
    await update_user(session, user.id, UserUpdate(weekly_digest_day=day))
    user.weekly_digest_day = day

    await callback.answer(t("settings.saved", lang))
    await show_notification_settings(callback, user, lang)


@router.callback_query(SettingsCb.filter(F.action == "digest_time"))
async def settings_digest_time(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    lang: str,
) -> None:
    text = t("settings.change_time", lang)
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
    await state.set_state(SettingsStates.waiting_digest_time)
    await callback.answer()


@router.message(SettingsStates.waiting_digest_time)
async def settings_set_digest_time(
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

    await update_user(session, user.id, UserUpdate(weekly_digest_time=new_time))
    user.weekly_digest_time = new_time
    await state.clear()
    await message.answer(
        t("settings.saved", lang),
        reply_markup=notification_settings_kb(user, lang),
    )


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
