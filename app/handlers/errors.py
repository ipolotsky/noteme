"""Global error handler for the bot."""

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from app.i18n.loader import t

logger = logging.getLogger(__name__)
router = Router(name="errors")


@router.error()
async def error_handler(event: ErrorEvent) -> bool:
    logger.exception(
        "Update %s caused exception: %s",
        event.update.update_id if event.update else "?",
        event.exception,
    )

    # Try to send an error message to the user
    update = event.update
    try:
        if update.message:
            lang = "ru"  # Fallback — middleware may not have run
            await update.message.answer(t("errors.unknown", lang))
        elif update.callback_query:
            await update.callback_query.answer(
                t("errors.unknown", "ru"), show_alert=True
            )
    except Exception:
        logger.exception("Failed to send error message to user")

    return True  # Error handled, stop propagation
