"""Feed inline keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import FeedCb, MenuCb
from app.keyboards.pagination import pagination_row
from app.models.beautiful_date import BeautifulDate

PAGE_SIZE = 5


def feed_list_kb(
    items: list[BeautifulDate], page: int, total: int, lang: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for bd in items:
        label = bd.label_ru if lang == "ru" else bd.label_en
        rows.append([InlineKeyboardButton(
            text=f"\U0001f52e {bd.target_date.strftime('%d.%m.%Y')} — {label[:50]}",
            callback_data=FeedCb(action="view", id=str(bd.id)).pack(),
        )])

    if total > PAGE_SIZE:
        rows.append(pagination_row("feed", page, total, PAGE_SIZE, lang))

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def feed_item_kb(bd: BeautifulDate, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"\U0001f517 {t('feed.share', lang)}",
            callback_data=FeedCb(action="share", id=str(bd.id)).pack(),
        )],
        [InlineKeyboardButton(
            text=f"\u25c0 {t('menu.back', lang)}",
            callback_data=FeedCb(action="list").pack(),
        )],
    ])
