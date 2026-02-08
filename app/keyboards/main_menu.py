"""Main menu keyboard."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.i18n.loader import t
from app.keyboards.callbacks import MenuCb


def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    """Keyboard with a single 'Cancel' button for FSM text-input states."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"\u2716 {t('menu.cancel', lang)}",
            callback_data="cancel",
        )],
    ])


def onboarding_skip_kb(lang: str) -> InlineKeyboardMarkup:
    """Keyboard with a 'Skip' button for onboarding steps."""
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
                text=f"\U0001f4dd {t('menu.notes', lang)}",
                callback_data=MenuCb(action="notes").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"\U0001f3f7 {t('menu.tags', lang)}",
                callback_data=MenuCb(action="tags").pack(),
            ),
            InlineKeyboardButton(
                text=f"\u2699\ufe0f {t('menu.settings', lang)}",
                callback_data=MenuCb(action="settings").pack(),
            ),
        ],
    ])


def persistent_menu_kb(lang: str) -> ReplyKeyboardMarkup:
    """Persistent reply keyboard — always visible at the bottom of the chat."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=f"\U0001f4c5 {t('menu.feed', lang)}"),
                KeyboardButton(text=f"\U0001f4cb {t('menu.events', lang)}"),
            ],
            [
                KeyboardButton(text=f"\U0001f4dd {t('menu.notes', lang)}"),
                KeyboardButton(text=f"\U0001f3f7 {t('menu.tags', lang)}"),
            ],
            [
                KeyboardButton(text=f"\u2699\ufe0f {t('menu.settings', lang)}"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
