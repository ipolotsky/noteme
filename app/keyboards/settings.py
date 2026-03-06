from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import MenuCb, SettingsCb
from app.models.user import User


def settings_kb(user: User, lang: str) -> InlineKeyboardMarkup:
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
            text=f"\U0001f514 {t('settings.notification_submenu', lang)}",
            callback_data=SettingsCb(action="notif_submenu").pack(),
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


def notification_settings_kb(user: User, lang: str) -> InlineKeyboardMarkup:
    enabled = t("settings.enabled", lang)
    disabled = t("settings.disabled", lang)

    notif_status = enabled if user.notifications_enabled else disabled
    day_status = enabled if user.notify_day_before else disabled
    week_status = enabled if user.notify_week_before else disabled
    digest_status = enabled if user.notify_weekly_digest else disabled

    day_of_week = t(f"days_of_week.{user.weekly_digest_day}", lang)

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("settings.notifications", lang, status=notif_status),
            callback_data=SettingsCb(action="notif_toggle").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.notify_day_before", lang, status=day_status),
            callback_data=SettingsCb(action="day_before_toggle").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.notify_day_before_time", lang, time=user.notify_day_before_time.strftime("%H:%M")),
            callback_data=SettingsCb(action="day_before_time").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.notify_week_before", lang, status=week_status),
            callback_data=SettingsCb(action="week_before_toggle").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.notify_week_before_time", lang, time=user.notify_week_before_time.strftime("%H:%M")),
            callback_data=SettingsCb(action="week_before_time").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.notify_weekly_digest", lang, status=digest_status),
            callback_data=SettingsCb(action="digest_toggle").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.weekly_digest_day", lang, day=day_of_week),
            callback_data=SettingsCb(action="digest_day").pack(),
        )],
        [InlineKeyboardButton(
            text=t("settings.weekly_digest_time", lang, time=user.weekly_digest_time.strftime("%H:%M")),
            callback_data=SettingsCb(action="digest_time").pack(),
        )],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=SettingsCb(action="view").pack(),
        )],
    ])


def digest_day_select_kb(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for i in range(7):
        rows.append([InlineKeyboardButton(
            text=t(f"days_of_week.{i}", lang),
            callback_data=SettingsCb(action="set_digest_day", value=str(i)).pack(),
        )])
    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=SettingsCb(action="notif_submenu").pack(),
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_select_kb(back_lang: str | None = None) -> InlineKeyboardMarkup:
    from app.keyboards.callbacks import LangCb
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
