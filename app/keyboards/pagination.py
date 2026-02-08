"""Pagination utility for inline keyboards."""

from aiogram.types import InlineKeyboardButton

from app.i18n.loader import t
from app.keyboards.callbacks import PageCb


def pagination_row(
    target: str, current_page: int, total_items: int, page_size: int, lang: str
) -> list[InlineKeyboardButton]:
    """Build a row of pagination buttons [< Prev] [page/total] [Next >]."""
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    buttons: list[InlineKeyboardButton] = []

    if current_page > 0:
        buttons.append(InlineKeyboardButton(
            text=f"\u25c0 {t('buttons.prev', lang)}",
            callback_data=PageCb(target=target, page=current_page - 1).pack(),
        ))

    buttons.append(InlineKeyboardButton(
        text=f"{current_page + 1}/{total_pages}",
        callback_data="noop",
    ))

    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton(
            text=f"{t('buttons.next', lang)} \u25b6",
            callback_data=PageCb(target=target, page=current_page + 1).pack(),
        ))

    return buttons
