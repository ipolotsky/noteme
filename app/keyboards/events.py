"""Event-related inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import EventCb, EventEditCb, MenuCb
from app.keyboards.pagination import pagination_row
from app.models.event import Event

PAGE_SIZE = 5


def events_list_kb(
    events: list[Event], page: int, total: int, lang: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for ev in events:
        rows.append([InlineKeyboardButton(
            text=f"\U0001f4c5 {ev.title} — {ev.event_date.strftime('%d.%m.%Y')}",
            callback_data=EventCb(action="view", id=str(ev.id)).pack(),
        )])

    rows.append([InlineKeyboardButton(
        text=f"\u2795 {t('events.create', lang)}",
        callback_data=EventCb(action="create").pack(),
    )])

    if total > PAGE_SIZE:
        rows.append(pagination_row("events", page, total, PAGE_SIZE, lang))

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_view_kb(event: Event, lang: str) -> InlineKeyboardMarkup:
    eid = str(event.id)
    rows: list[list[InlineKeyboardButton]] = []

    rows.append([
        InlineKeyboardButton(
            text=f"\u270f\ufe0f {t('events.edit', lang)}",
            callback_data=EventCb(action="edit", id=eid).pack(),
        ),
        InlineKeyboardButton(
            text=f"\U0001f5d1 {t('events.delete', lang)}",
            callback_data=EventCb(action="delete", id=eid).pack(),
        ),
    ])

    rows.append([InlineKeyboardButton(
        text=f"\U0001f52e {t('events.beautiful_dates', lang)}",
        callback_data=EventCb(action="dates", id=eid).pack(),
    )])

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=EventCb(action="list").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_edit_kb(event_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("events.create_title", lang).rstrip(":"),
            callback_data=EventEditCb(field="title", id=event_id).pack(),
        )],
        [InlineKeyboardButton(
            text=t("events.create_date", lang).rstrip(":"),
            callback_data=EventEditCb(field="date", id=event_id).pack(),
        )],
        [InlineKeyboardButton(
            text=t("events.create_description", lang).rstrip(":"),
            callback_data=EventEditCb(field="description", id=event_id).pack(),
        )],
        [InlineKeyboardButton(
            text=t("events.create_tags", lang).rstrip(":"),
            callback_data=EventEditCb(field="tags", id=event_id).pack(),
        )],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=EventCb(action="view", id=event_id).pack(),
        )],
    ])


def event_delete_confirm_kb(event_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t("buttons.yes", lang),
                callback_data=EventCb(action="confirm_delete", id=event_id).pack(),
            ),
            InlineKeyboardButton(
                text=t("buttons.no", lang),
                callback_data=EventCb(action="view", id=event_id).pack(),
            ),
        ],
    ])


def event_skip_kb(lang: str) -> InlineKeyboardMarkup:
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
