"""Agent registry, checkpointer wiring, and Langfuse handler."""

from __future__ import annotations

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.agents.main_agent import agent as main_agent
from src.agents.order_agent import agent as order_agent
from src.agents.product_agent import agent as product_agent
from src.config.settings import settings

AGENTS = {
    "main": main_agent,
    "order": order_agent,
    "product": product_agent,
}


def wire_checkpointer(checkpointer: AsyncSqliteSaver) -> None:
    """Assign the async checkpointer to every registered agent.

    Called once during FastAPI lifespan startup.
    """
    for agent in AGENTS.values():
        agent.checkpointer = checkpointer


def get_agent(agent_name: str = "main"):
    """Return a compiled agent graph by name."""
    agent = AGENTS.get(agent_name)
    if agent is None:
        raise ValueError(f"Unknown agent_name: {agent_name!r}. Choose from {list(AGENTS)}")
    return agent


def get_langfuse_handler(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    app_id: str | None = None,
) -> dict:
    """Return a config dict with Langfuse callback and metadata.

    LANGFUSE_ENABLED=false ise boş dict döner.
    """
    if not settings.langfuse_enabled:
        return {}

    from langfuse.langchain import CallbackHandler

    handler = CallbackHandler()

    metadata: dict = {}
    if user_id:
        metadata["langfuse_user_id"] = user_id
    if session_id:
        metadata["langfuse_session_id"] = session_id
    if app_id:
        metadata["langfuse_app_id"] = app_id

    config: dict = {"callbacks": [handler]}
    if metadata:
        config["metadata"] = metadata
    return config
