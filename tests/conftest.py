"""Shared test fixtures."""

import os
import tempfile

import pytest
import httpx
from httpx import ASGITransport

# Ensure .env is loaded before any src imports
from dotenv import load_dotenv

load_dotenv()

# Force-disable Langfuse for tests (setdefault won't override .env values)
os.environ["LANGFUSE_ENABLED"] = "false"
os.environ["LANGFUSE_PROMPT_MANAGEMENT_ENABLED"] = "false"


PYTHON = "/home/serdar/miniconda3/envs/langchain/bin/python"

# LLM timeout for integration tests (seconds)
LLM_TIMEOUT = 120


@pytest.fixture
def valid_chat_request() -> dict:
    """Minimal valid ChatRequest payload."""
    return {
        "app_id": "test-app",
        "user_id": "test-user",
        "session_id": "test-sess",
        "messages": [{"role": "user", "content": "Hello"}],
    }


@pytest.fixture
async def app_client():
    """Async HTTP client with FastAPI app (triggers lifespan)."""
    from main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        timeout=LLM_TIMEOUT,
    ) as client:
        yield client


@pytest.fixture
async def temp_checkpointer():
    """Temporary SQLite checkpointer for isolated tests.

    After test, resets all agents' checkpointers to None to prevent
    stale connection references from affecting other tests.
    """
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = await aiosqlite.connect(db_path)
    saver = AsyncSqliteSaver(conn)
    yield saver

    # Reset agent checkpointers to avoid stale connection in other tests
    from src.providers import AGENTS
    for entry in AGENTS.values():
        entry["agent"].checkpointer = None

    await conn.close()
    os.unlink(db_path)
