"""Feed inline keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import EventCb, FeedCb, MenuCb
from app.models.beautiful_date import BeautifulDate


def feed_card_kb(bd: BeautifulDate, offset: int, total: int, lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    nav_row: list[InlineKeyboardButton] = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text=f"\u25c0 {t('feed.prev', lang)}",
            callback_data=FeedCb(action="card", page=offset - 1).pack(),
        ))
    if offset < total - 1:
        nav_row.append(InlineKeyboardButton(
            text=f"{t('feed.next', lang)} \u25b6",
            callback_data=FeedCb(action="card", page=offset + 1).pack(),
        ))
    if nav_row:
        rows.append(nav_row)

    rows.append([
        InlineKeyboardButton(
            text=f"\U0001f4c5 {t('feed.to_event', lang)}",
            callback_data=EventCb(action="view_new", id=str(bd.event_id)).pack(),
        ),
        InlineKeyboardButton(
            text=f"\U0001f4cb {t('feed.all_wishes', lang)}",
            callback_data=FeedCb(action="wishes", id=str(bd.id)).pack(),
        ),
    ])

    rows.append([InlineKeyboardButton(
        text=f"\U0001f517 {t('feed.share', lang)}",
        callback_data=FeedCb(action="share", id=str(bd.id)).pack(),
    )])

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)
