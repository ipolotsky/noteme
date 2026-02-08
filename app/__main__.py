import asyncio
import logging
import signal

import uvicorn

from app.bot import bot, dp
from app.config import settings

logger = logging.getLogger(__name__)

_shutdown_event = asyncio.Event()


def _signal_handler() -> None:
    logger.info("Received shutdown signal")
    _shutdown_event.set()


async def start_bot() -> None:
    logger.info("Starting Noteme bot polling...")
    await dp.start_polling(bot)


async def start_web() -> None:
    config = uvicorn.Config(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    logger.info("Starting FastAPI on %s:%s", settings.app_host, settings.app_port)
    await server.serve()


async def shutdown() -> None:
    """Graceful shutdown: close DB engine, Redis cache, bot session."""
    logger.info("Shutting down gracefully...")

    # Stop bot polling
    await dp.stop_polling()

    # Close bot session
    await bot.session.close()

    # Close DB engine
    from app.database import engine
    await engine.dispose()

    # Close Redis cache
    from app.services.cache import close_cache
    await close_cache()

    logger.info("Shutdown complete.")


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    logger.info("Starting Noteme...")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        await asyncio.gather(
            start_bot(),
            start_web(),
        )
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
