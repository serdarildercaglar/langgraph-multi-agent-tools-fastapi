"""Layer 5b: Message trimming middleware tests."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from src.middleware.trim import trim_old_messages


def _make_state(n_pairs: int, system: bool = True) -> dict:
    """Build a fake state dict with system + n human/ai pairs."""
    messages = []
    if system:
        messages.append(SystemMessage(content="You are helpful."))
    for i in range(n_pairs):
        messages.append(HumanMessage(content=f"Question {i}" * 50))  # make it long
        messages.append(AIMessage(content=f"Answer {i}" * 50))
    return {"messages": messages}


def test_no_trim_short():
    """4 or fewer messages → no trimming (returns None)."""
    state = _make_state(1, system=True)  # system + 1 human + 1 ai = 3
    # trim_old_messages is a @before_model middleware; call its inner function
    result = trim_old_messages.before_model(state, None)
    assert result is None


def test_no_trim_exactly_four():
    state = {"messages": [
        SystemMessage(content="sys"),
        HumanMessage(content="q1"),
        AIMessage(content="a1"),
        HumanMessage(content="q2"),
    ]}
    result = trim_old_messages.before_model(state, None)
    assert result is None


def test_trim_long():
    """Many messages exceeding token limit → trimming occurs."""
    state = _make_state(20, system=True)  # 41 messages, lots of tokens
    result = trim_old_messages.before_model(state, None)
    assert result is not None
    assert "messages" in result
    assert len(result["messages"]) < len(state["messages"])


def test_system_preserved():
    """System message is preserved after trimming."""
    state = _make_state(20, system=True)
    result = trim_old_messages.before_model(state, None)
    assert result is not None
    # Find non-RemoveMessage messages
    kept = [m for m in result["messages"] if not isinstance(m, RemoveMessage)]
    system_msgs = [m for m in kept if isinstance(m, SystemMessage)]
    assert len(system_msgs) >= 1


def test_remove_all_in_result():
    """Trimmed result starts with RemoveMessage(id=REMOVE_ALL_MESSAGES)."""
    state = _make_state(20, system=True)
    result = trim_old_messages.before_model(state, None)
    assert result is not None
    first = result["messages"][0]
    assert isinstance(first, RemoveMessage)
    assert first.id == REMOVE_ALL_MESSAGES
