from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.sharing import router as sharing_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    yield
    # Shutdown
    from app.database import engine

    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Noteme",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(sharing_router)

    # Admin panel
    from app.admin.setup import setup_admin
    setup_admin(app)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    return app


app = create_app()
