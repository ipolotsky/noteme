"""Logging middleware — logs every incoming update + user action tracking."""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        start = time.monotonic()
        user_id = None
        event_type = type(event).__name__

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            detail = event.text[:50] if event.text else event.content_type
            logger.info("Message from %s: %s", user_id, detail)
            # Log callback actions to user action log
            if user_id:
                await self._log_action(user_id, "message", detail)
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            logger.info("Callback from %s: %s", user_id, event.data)
            if user_id:
                await self._log_action(user_id, "callback", event.data)

        try:
            result = await handler(event, data)
            elapsed = (time.monotonic() - start) * 1000
            logger.debug("%s from %s handled in %.0fms", event_type, user_id, elapsed)
            return result
        except Exception:
            elapsed = (time.monotonic() - start) * 1000
            logger.exception(
                "%s from %s failed after %.0fms", event_type, user_id, elapsed
            )
            raise

    @staticmethod
    async def _log_action(user_id: int, action: str, detail: str | None) -> None:
        try:
            from app.services.action_logger import log_user_action
            await log_user_action(user_id, action, detail)
        except Exception:
            logger.debug("Action logging failed (non-critical)", exc_info=True)
