"""Async checkpointer for LangGraph agents.

AsyncSqliteSaver async context gerektirir. Bu modül FastAPI lifespan
ile birlikte kullanılır:

    1. Uygulama başlarken: await init_checkpointer()
    2. Uygulama kapanırken: await shutdown_checkpointer()

Agent'lara checkpointer atama işi providers.py'de yapılır.
"""

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_checkpointer: AsyncSqliteSaver | None = None
_conn: aiosqlite.Connection | None = None


async def init_checkpointer() -> AsyncSqliteSaver:
    """Create and return an AsyncSqliteSaver instance.

    Called once during FastAPI lifespan startup.
    """
    global _checkpointer, _conn
    _conn = await aiosqlite.connect("checkpoints.db")
    _checkpointer = AsyncSqliteSaver(_conn)
    return _checkpointer


async def shutdown_checkpointer() -> None:
    """Close the database connection.

    Called once during FastAPI lifespan shutdown.
    """
    global _checkpointer, _conn
    if _conn is not None:
        await _conn.close()
    _checkpointer = None
    _conn = None


def get_checkpointer() -> AsyncSqliteSaver | None:
    """Return the current checkpointer instance (None before init)."""
    return _checkpointer
