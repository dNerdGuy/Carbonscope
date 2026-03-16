"""SQLAlchemy async engine + session factory.

Supports both SQLite (aiosqlite) and PostgreSQL (asyncpg).
PostgreSQL uses connection pooling for production performance.
"""

from __future__ import annotations

import logging
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from api.config import DATABASE_URL, DB_SLOW_QUERY_MS

logger = logging.getLogger(__name__)

_is_sqlite = DATABASE_URL.startswith("sqlite")

# PostgreSQL connection pooling settings
_engine_kwargs: dict = {"echo": False}
if not _is_sqlite:
    _engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,  # recycle connections every 30 min
        "pool_pre_ping": True,  # test connections before use
    })

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
_SLOW_QUERY_TIMER_KEY = "carbonscope_query_start_times"


if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, connection_record):
        """Enable foreign-key enforcement for every SQLite connection."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query start timestamps for slow-query logging."""
    start_times = conn.info.setdefault(_SLOW_QUERY_TIMER_KEY, [])
    start_times.append(perf_counter())


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Emit a warning when query time exceeds DB_SLOW_QUERY_MS."""
    start_times = conn.info.get(_SLOW_QUERY_TIMER_KEY)
    if not start_times:
        return

    started_at = start_times.pop()
    elapsed_ms = (perf_counter() - started_at) * 1000.0
    if elapsed_ms >= DB_SLOW_QUERY_MS:
        # Keep logs compact while still making the query identifiable.
        compact = " ".join(str(statement).split())
        if len(compact) > 300:
            compact = compact[:300] + "..."
        logger.warning(
            "Slow query detected: %.1fms (threshold=%dms) sql=%s",
            elapsed_ms,
            DB_SLOW_QUERY_MS,
            compact,
        )


async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields an async DB session."""
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """Create all tables (development convenience — use Alembic in production)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_db_pool_status() -> str:
    """Return a compact pool status string for health checks."""
    if _is_sqlite:
        return "sqlite/no_pool"
    try:
        return engine.sync_engine.pool.status()
    except Exception:
        return "unavailable"
