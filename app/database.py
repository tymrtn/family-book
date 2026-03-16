import os
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def _build_url(url: str) -> str:
    """Convert sqlite:/// to sqlite+aiosqlite:/// for async support."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def _set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


settings = get_settings()
engine = create_async_engine(
    _build_url(settings.DATABASE_URL),
    echo=False,
)
event.listens_for(engine.sync_engine, "connect")(_set_sqlite_pragmas)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_test_engine(url: str = "sqlite+aiosqlite://"):
    """Create an in-memory engine for tests."""
    test_engine = create_async_engine(url, echo=False)
    event.listens_for(test_engine.sync_engine, "connect")(_set_sqlite_pragmas)
    return test_engine
