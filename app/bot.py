"""Aiogram bot setup — dispatcher, middlewares, routers."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.config import settings
from app.handlers import ai, common, errors, events, feed, notes, start, tags
from app.handlers import settings as settings_handler
from app.middlewares import (
    DbSessionMiddleware,
    I18nMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    UserMiddleware,
)

storage = RedisStorage.from_url(settings.redis_url)

dp = Dispatcher(storage=storage)

bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# --- Register middlewares (order matters: outer → inner) ---
# Message middlewares
dp.message.outer_middleware(LoggingMiddleware())
dp.message.outer_middleware(DbSessionMiddleware())
dp.message.outer_middleware(UserMiddleware())
dp.message.outer_middleware(I18nMiddleware())
dp.message.outer_middleware(RateLimitMiddleware())

# Callback query middlewares
dp.callback_query.outer_middleware(LoggingMiddleware())
dp.callback_query.outer_middleware(DbSessionMiddleware())
dp.callback_query.outer_middleware(UserMiddleware())
dp.callback_query.outer_middleware(I18nMiddleware())

# --- Register routers (order matters for handler priority) ---
dp.include_router(errors.router)
dp.include_router(start.router)
dp.include_router(common.router)
dp.include_router(events.router)
dp.include_router(feed.router)
dp.include_router(notes.router)
dp.include_router(tags.router)
dp.include_router(settings_handler.router)
dp.include_router(ai.router)  # Must be last — catches all text/voice
