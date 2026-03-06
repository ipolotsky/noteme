from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.i18n.loader import t
from app.keyboards.callbacks import MenuCb


def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"\u2716 {t('menu.cancel', lang)}",
            callback_data="cancel",
        )],
    ])


def onboarding_skip_kb(lang: str) -> InlineKeyboardMarkup:
    from app.keyboards.callbacks import OnboardCb
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"\u23ed {t('onboarding.skip', lang)}",
            callback_data=OnboardCb(action="skip").pack(),
        )],
    ])


def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"\U0001f4c5 {t('menu.feed', lang)}",
            callback_data=MenuCb(action="feed").pack(),
        )],
        [
            InlineKeyboardButton(
                text=f"\U0001f4cb {t('menu.events', lang)}",
                callback_data=MenuCb(action="events").pack(),
            ),
            InlineKeyboardButton(
                text=f"\U0001f381 {t('menu.wishes', lang)}",
                callback_data=MenuCb(action="wishes").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"\U0001f464 {t('menu.people', lang)}",
                callback_data=MenuCb(action="people").pack(),
            ),
            InlineKeyboardButton(
                text=f"\u2699\ufe0f {t('menu.settings', lang)}",
                callback_data=MenuCb(action="settings").pack(),
            ),
        ],
    ])


def persistent_menu_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=f"\U0001f4c5 {t('menu.feed', lang)}"),
                KeyboardButton(text=f"\U0001f4cb {t('menu.events', lang)}"),
            ],
            [
                KeyboardButton(text=f"\U0001f381 {t('menu.wishes', lang)}"),
                KeyboardButton(text=f"\U0001f464 {t('menu.people', lang)}"),
            ],
            [
                KeyboardButton(text=f"\u2699\ufe0f {t('menu.settings', lang)}"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
