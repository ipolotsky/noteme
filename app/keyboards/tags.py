"""Tag-related inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import MenuCb, TagCb
from app.keyboards.pagination import pagination_row
from app.models.tag import Tag

PAGE_SIZE = 10


def tags_list_kb(
    tags: list[Tag], page: int, total: int, lang: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for tag in tags:
        rows.append([InlineKeyboardButton(
            text=f"\U0001f3f7 {tag.name}",
            callback_data=TagCb(action="view", id=str(tag.id)).pack(),
        )])

    rows.append([InlineKeyboardButton(
        text=f"\u2795 {t('tags.create', lang)}",
        callback_data=TagCb(action="create").pack(),
    )])

    if total > PAGE_SIZE:
        rows.append(pagination_row("tags", page, total, PAGE_SIZE, lang))

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def tag_view_kb(tag: Tag, lang: str) -> InlineKeyboardMarkup:
    tid = str(tag.id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"\u270f\ufe0f {t('tags.rename', lang)}",
                callback_data=TagCb(action="rename", id=tid).pack(),
            ),
            InlineKeyboardButton(
                text=f"\U0001f5d1 {t('tags.delete', lang)}",
                callback_data=TagCb(action="delete", id=tid).pack(),
            ),
        ],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=TagCb(action="list").pack(),
        )],
    ])


def tag_delete_confirm_kb(tag_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t("buttons.yes", lang),
                callback_data=TagCb(action="confirm_delete", id=tag_id).pack(),
            ),
            InlineKeyboardButton(
                text=t("buttons.no", lang),
                callback_data=TagCb(action="view", id=tag_id).pack(),
            ),
        ],
    ])
