"""Note-related inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import MenuCb, NoteCb, NoteEditCb
from app.keyboards.pagination import pagination_row
from app.models.note import Note

PAGE_SIZE = 5


def notes_list_kb(
    notes: list[Note], page: int, total: int, lang: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for note in notes:
        preview = note.text[:40] + ("..." if len(note.text) > 40 else "")
        rows.append([InlineKeyboardButton(
            text=f"\U0001f4dd {preview}",
            callback_data=NoteCb(action="view", id=str(note.id)).pack(),
        )])

    rows.append([InlineKeyboardButton(
        text=f"\u2795 {t('notes.create', lang)}",
        callback_data=NoteCb(action="create").pack(),
    )])

    if total > PAGE_SIZE:
        rows.append(pagination_row("notes", page, total, PAGE_SIZE, lang))

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def note_view_kb(note: Note, lang: str) -> InlineKeyboardMarkup:
    nid = str(note.id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"\u270f\ufe0f {t('notes.edit', lang)}",
                callback_data=NoteCb(action="edit", id=nid).pack(),
            ),
            InlineKeyboardButton(
                text=f"\U0001f5d1 {t('notes.delete', lang)}",
                callback_data=NoteCb(action="delete", id=nid).pack(),
            ),
        ],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=NoteCb(action="list").pack(),
        )],
    ])


def note_edit_kb(note_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("notes.create_text", lang).rstrip(":"),
            callback_data=NoteEditCb(field="text", id=note_id).pack(),
        )],
        [InlineKeyboardButton(
            text=t("notes.create_reminder", lang).split("?")[0],
            callback_data=NoteEditCb(field="reminder", id=note_id).pack(),
        )],
        [InlineKeyboardButton(
            text=t("notes.create_tags", lang).rstrip(":"),
            callback_data=NoteEditCb(field="tags", id=note_id).pack(),
        )],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=NoteCb(action="view", id=note_id).pack(),
        )],
    ])


def note_delete_confirm_kb(note_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t("buttons.yes", lang),
                callback_data=NoteCb(action="confirm_delete", id=note_id).pack(),
            ),
            InlineKeyboardButton(
                text=t("buttons.no", lang),
                callback_data=NoteCb(action="view", id=note_id).pack(),
            ),
        ],
    ])


def note_skip_kb(lang: str) -> InlineKeyboardMarkup:
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
