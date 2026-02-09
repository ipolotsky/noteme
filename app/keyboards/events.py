"""Event-related inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import EventCb, EventEditCb, MenuCb, TagCb
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


def event_view_kb(
    event: Event,
    lang: str,
    related_notes_count: int = 0,
    tag_event_counts: dict[str, tuple[str, int]] | None = None,
) -> InlineKeyboardMarkup:
    """Build event view keyboard.

    tag_event_counts: {tag_name: (tag_id, event_count)} for per-tag buttons.
    """
    eid = str(event.id)
    rows: list[list[InlineKeyboardButton]] = []

    # Row 1: Edit + Delete
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

    # Row 2: Beautiful dates
    rows.append([InlineKeyboardButton(
        text=f"\U0001f52e {t('events.beautiful_dates', lang)}",
        callback_data=EventCb(action="dates", id=eid).pack(),
    )])

    # Row 3: Related notes (if any)
    if related_notes_count > 0:
        rows.append([InlineKeyboardButton(
            text=f"\U0001f4dd {t('events.related_notes', lang)} ({related_notes_count})",
            callback_data=EventCb(action="related_notes", id=eid).pack(),
        )])

    # Per-tag event buttons (only if >1 event with that tag)
    if tag_event_counts:
        for tag_name, (tag_id, count) in tag_event_counts.items():
            if count > 1:
                label = t("events.events_with_tag", lang, tag=tag_name)
                rows.append([InlineKeyboardButton(
                    text=f"\U0001f4cb {label} ({count})",
                    callback_data=TagCb(action="events", id=tag_id).pack(),
                )])

    # Back
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
