"""i18n middleware — injects user language and t() shortcut into handler data."""

from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.i18n.loader import DEFAULT_LANGUAGE, t

if TYPE_CHECKING:
    from app.models.user import User


class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("user")
        lang = user.language if user else DEFAULT_LANGUAGE
        data["lang"] = lang
        data["t"] = partial(t, lang=lang)
        return await handler(event, data)
