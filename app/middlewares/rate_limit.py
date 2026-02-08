"""Simple rate-limit middleware using Redis."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.i18n.loader import t


class RateLimitMiddleware(BaseMiddleware):
    """Per-user message rate limiter.

    Limits total messages (not AI calls — those are limited separately).
    Uses a simple in-memory counter with TTL check per minute.
    """

    def __init__(self, max_per_minute: int = 60) -> None:
        self.max_per_minute = max_per_minute
        self._counters: dict[int, list[float]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)

        import time

        user_id = event.from_user.id
        now = time.monotonic()
        window = self._counters.setdefault(user_id, [])

        # Remove timestamps older than 60s
        window[:] = [ts for ts in window if now - ts < 60]

        if len(window) >= self.max_per_minute:
            lang = data.get("lang", "ru")
            await event.answer(t("ai.rate_limit", lang))
            return None

        window.append(now)
        return await handler(event, data)
