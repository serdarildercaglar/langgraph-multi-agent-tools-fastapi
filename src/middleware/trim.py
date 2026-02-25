"""Trim messages middleware — keeps conversation history within token limit.

LLM çağrısından önce çalışır. Eski mesajları kırpar, system prompt'u korur.
Kırpılan mesajlar checkpoint'ten de silinir (RemoveMessage + REMOVE_ALL_MESSAGES).
"""

from langchain.agents.middleware import before_model
from langchain_core.messages import RemoveMessage
from langchain_core.messages.utils import trim_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from src.config.settings import settings


@before_model
def trim_old_messages(state, runtime):
    """Keep only the last N tokens of messages before each LLM call."""
    messages = state["messages"]
    if len(messages) <= 4:
        return None

    trimmed = trim_messages(
        messages,
        strategy="last",
        token_counter="approximate",
        max_tokens=settings.chat_history_max_tokens,
        include_system=True,
        start_on="human",
    )

    if len(trimmed) == len(messages):
        return None

    return {
        "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *trimmed],
    }
