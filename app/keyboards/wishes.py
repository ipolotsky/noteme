from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import MenuCb, WishCb, WishEditCb
from app.keyboards.pagination import pagination_row
from app.models.wish import Wish

PAGE_SIZE = 5


def wishes_list_kb(
    wishes: list[Wish], page: int, total: int, lang: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for wish in wishes:
        preview = wish.text[:40] + ("..." if len(wish.text) > 40 else "")
        rows.append([InlineKeyboardButton(
            text=f"\U0001f4dd {preview}",
            callback_data=WishCb(action="view", id=str(wish.id)).pack(),
        )])

    rows.append([InlineKeyboardButton(
        text=f"\u2795 {t('wishes.create', lang)}",
        callback_data=WishCb(action="create").pack(),
    )])

    if total > PAGE_SIZE:
        rows.append(pagination_row("wishes", page, total, PAGE_SIZE, lang))

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def wish_view_kb(wish: Wish, lang: str) -> InlineKeyboardMarkup:
    wid = str(wish.id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"\u270f\ufe0f {t('wishes.edit', lang)}",
                callback_data=WishCb(action="edit", id=wid).pack(),
            ),
            InlineKeyboardButton(
                text=f"\U0001f5d1 {t('wishes.delete', lang)}",
                callback_data=WishCb(action="delete", id=wid).pack(),
            ),
        ],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=WishCb(action="list").pack(),
        )],
    ])


def wish_edit_kb(wish_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("wishes.create_text", lang).rstrip(":"),
            callback_data=WishEditCb(field="text", id=wish_id).pack(),
        )],
        [InlineKeyboardButton(
            text=t("wishes.create_reminder", lang).split("?")[0],
            callback_data=WishEditCb(field="reminder", id=wish_id).pack(),
        )],
        [InlineKeyboardButton(
            text=t("wishes.create_people", lang).rstrip(":"),
            callback_data=WishEditCb(field="people", id=wish_id).pack(),
        )],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=WishCb(action="view", id=wish_id).pack(),
        )],
    ])


def wish_delete_confirm_kb(wish_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t("buttons.yes", lang),
                callback_data=WishCb(action="confirm_delete", id=wish_id).pack(),
            ),
            InlineKeyboardButton(
                text=t("buttons.no", lang),
                callback_data=WishCb(action="view", id=wish_id).pack(),
            ),
        ],
    ])


def wish_skip_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("buttons.skip", lang),
            callback_data="skip",
        )],
        [InlineKeyboardButton(
            text=f"\u2716 {t('menu.cancel', lang)}",
            callback_data="cancel",
        )],
    ])
