"""SQLAlchemy async engine + session factory."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from api.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_fk(dbapi_conn, connection_record):
    """Enable foreign-key enforcement for every SQLite connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields an async DB session."""
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """Create all tables (development convenience)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
