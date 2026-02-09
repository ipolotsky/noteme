"""Test configuration with async PostgreSQL session.

IMPORTANT: Tests use a SEPARATE database (noteme_test) to avoid
destroying dev/prod data. The main 'noteme' database is never touched.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import all models so metadata is populated
import app.models  # noqa: F401
from app.config import settings
from app.models.base import Base

# Build test DB URL: replace db_name with 'noteme_test'
_TEST_DB_URL = settings.database_url.rsplit("/", 1)[0] + "/noteme_test"


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean test session per test.

    Creates tables in noteme_test, yields session, then drops all tables.
    Each test gets a fresh database state. The main 'noteme' DB is untouched.
    """
    engine = create_async_engine(_TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    # Clean up: drop all tables in TEST db only
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def user_id() -> int:
    """Sample Telegram user_id."""
    return 123456789
