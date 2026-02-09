"""Tag-related inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import MediaTagCb, MenuCb, TagCb
from app.keyboards.pagination import pagination_row
from app.models.tag import Tag

PAGE_SIZE = 10


def tags_list_kb(
    tags: list[Tag], page: int, total: int, lang: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    # Tags in 2 columns
    for i in range(0, len(tags), 2):
        row = [InlineKeyboardButton(
            text=f"\U0001f3f7 {tags[i].name}",
            callback_data=TagCb(action="view", id=str(tags[i].id)).pack(),
        )]
        if i + 1 < len(tags):
            row.append(InlineKeyboardButton(
                text=f"\U0001f3f7 {tags[i + 1].name}",
                callback_data=TagCb(action="view", id=str(tags[i + 1].id)).pack(),
            ))
        rows.append(row)

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


def tag_view_kb(
    tag: Tag, lang: str, events_count: int = 0, notes_count: int = 0,
) -> InlineKeyboardMarkup:
    tid = str(tag.id)
    rows: list[list[InlineKeyboardButton]] = []

    # Events / Notes buttons (only if count > 0)
    browse_row: list[InlineKeyboardButton] = []
    if events_count > 0:
        browse_row.append(InlineKeyboardButton(
            text=f"\U0001f4cb {t('tags.show_events', lang)} ({events_count})",
            callback_data=TagCb(action="events", id=tid).pack(),
        ))
    if notes_count > 0:
        browse_row.append(InlineKeyboardButton(
            text=f"\U0001f4dd {t('tags.show_notes', lang)} ({notes_count})",
            callback_data=TagCb(action="notes", id=tid).pack(),
        ))
    if browse_row:
        rows.append(browse_row)

    rows.append([
        InlineKeyboardButton(
            text=f"\u270f\ufe0f {t('tags.rename', lang)}",
            callback_data=TagCb(action="rename", id=tid).pack(),
        ),
        InlineKeyboardButton(
            text=f"\U0001f5d1 {t('tags.delete', lang)}",
            callback_data=TagCb(action="delete", id=tid).pack(),
        ),
    ])
    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=TagCb(action="list").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def media_tag_select_kb(tags: list[Tag], lang: str) -> InlineKeyboardMarkup:
    """Tag selection keyboard for media messages — 2 columns."""
    rows: list[list[InlineKeyboardButton]] = []

    for i in range(0, len(tags), 2):
        row = [InlineKeyboardButton(
            text=f"\U0001f3f7 {tags[i].name}",
            callback_data=MediaTagCb(action="select", id=str(tags[i].id)).pack(),
        )]
        if i + 1 < len(tags):
            row.append(InlineKeyboardButton(
                text=f"\U0001f3f7 {tags[i + 1].name}",
                callback_data=MediaTagCb(action="select", id=str(tags[i + 1].id)).pack(),
            ))
        rows.append(row)

    rows.append([InlineKeyboardButton(
        text=f"\u2795 {t('tags.create', lang)}",
        callback_data=MediaTagCb(action="create").pack(),
    )])
    rows.append([InlineKeyboardButton(
        text=f"\u2716 {t('menu.cancel', lang)}",
        callback_data=MediaTagCb(action="cancel").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)
