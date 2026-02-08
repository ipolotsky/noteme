"""Settings inline keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import MenuCb, SettingsCb
from app.models.user import User


def settings_kb(user: User, lang: str) -> InlineKeyboardMarkup:
    notif_status = t("settings.enabled", lang) if user.notifications_enabled else t("settings.disabled", lang)
    spoiler_status = t("settings.enabled", lang) if user.spoiler_enabled else t("settings.disabled", lang)
    lang_label = "\U0001f1f7\U0001f1fa Русский" if lang == "ru" else "\U0001f1ec\U0001f1e7 English"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("settings.language", lang, language=lang_label),
            callback_data=SettingsCb(action="language").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.timezone", lang, tz=user.timezone),
            callback_data=SettingsCb(action="timezone").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.notifications", lang, status=notif_status),
            callback_data=SettingsCb(action="notif_toggle").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.notification_time", lang, time=user.notification_time.strftime("%H:%M")),
            callback_data=SettingsCb(action="notif_time").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.notification_count", lang, count=str(user.notification_count)),
            callback_data=SettingsCb(action="notif_count").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.spoiler", lang, status=spoiler_status),
            callback_data=SettingsCb(action="spoiler").pack(),
        )],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=MenuCb(action="main").pack(),
        )],
    ])


def language_select_kb(back_lang: str | None = None) -> InlineKeyboardMarkup:
    from app.keyboards.callbacks import LangCb, SettingsCb
    rows = [
        [
            InlineKeyboardButton(
                text="\U0001f1f7\U0001f1fa Русский",
                callback_data=LangCb(code="ru").pack(),
            ),
            InlineKeyboardButton(
                text="\U0001f1ec\U0001f1e7 English",
                callback_data=LangCb(code="en").pack(),
            ),
        ],
    ]
    if back_lang:
        rows.append([InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', back_lang)}",
            callback_data=SettingsCb(action="view").pack(),
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)
