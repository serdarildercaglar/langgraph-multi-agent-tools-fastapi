"""Layer 5a: Checkpointer lifecycle tests."""

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.memory.checkpointer import (
    get_checkpointer,
    init_checkpointer,
    shutdown_checkpointer,
)


async def test_get_before_init():
    """get_checkpointer returns None before initialization."""
    # Ensure clean state
    await shutdown_checkpointer()
    assert get_checkpointer() is None


async def test_init_returns_saver():
    cp = await init_checkpointer()
    try:
        assert isinstance(cp, AsyncSqliteSaver)
    finally:
        await shutdown_checkpointer()


async def test_get_after_init():
    await init_checkpointer()
    try:
        assert get_checkpointer() is not None
    finally:
        await shutdown_checkpointer()


async def test_shutdown_resets():
    await init_checkpointer()
    await shutdown_checkpointer()
    assert get_checkpointer() is None


async def test_wire_sets_all_agents():
    from src.providers import AGENTS, wire_checkpointer

    cp = await init_checkpointer()
    try:
        wire_checkpointer(cp)
        for entry in AGENTS.values():
            assert entry["agent"].checkpointer is cp
    finally:
        await shutdown_checkpointer()
