"""User upsert middleware — ensures user exists in DB for every update."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.schemas.user import UserCreate
from app.services.user_service import get_or_create_user

if TYPE_CHECKING:
    from aiogram.types import User as TgUser
    from sqlalchemy.ext.asyncio import AsyncSession


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        session: AsyncSession | None = data.get("session")

        if tg_user is not None and session is not None:
            user_data = UserCreate(
                id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name or "",
            )
            user, _ = await get_or_create_user(session, user_data)
            data["user"] = user

        return await handler(event, data)
