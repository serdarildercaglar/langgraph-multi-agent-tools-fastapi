"""Agent registry, checkpointer wiring, Langfuse handler, and discovery metadata."""

from __future__ import annotations

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.agents.billing_agent import agent as billing_agent
from src.agents.main_agent import agent as main_agent
from src.agents.subscription_agent import agent as subscription_agent
from src.agents.technical_agent import agent as technical_agent
from src.config.settings import settings

AGENTS = {
    "main": {
        "agent": main_agent,
        "description": "Customer support manager. Routes to subscription/billing/technical specialists.",
    },
    "subscription": {
        "agent": subscription_agent,
        "description": "Subscription specialist. Plan info, upgrades, comparisons, packages.",
    },
    "billing": {
        "agent": billing_agent,
        "description": "Billing specialist. Invoices, charges, payments, installment plans.",
    },
    "technical": {
        "agent": technical_agent,
        "description": "Technical support specialist. Network, diagnostics, device compatibility, trouble tickets.",
    },
}


def wire_checkpointer(checkpointer: AsyncSqliteSaver) -> None:
    """Assign the async checkpointer to every registered agent.

    Called once during FastAPI lifespan startup.
    """
    for entry in AGENTS.values():
        entry["agent"].checkpointer = checkpointer


def get_agent(agent_name: str = "main"):
    """Return a compiled agent graph by name."""
    entry = AGENTS.get(agent_name)
    if entry is None:
        raise ValueError(f"Unknown agent_name: {agent_name!r}. Choose from {list(AGENTS)}")
    return entry["agent"]


def _extract_tools(agent) -> list[dict]:
    """Extract tool metadata from a compiled agent's graph."""
    tools_node = agent.nodes.get("tools")
    if not tools_node:
        return []
    bound = getattr(tools_node, "bound", None)
    if not bound:
        return []
    tools_by_name = getattr(bound, "tools_by_name", {})
    result = []
    for tool_obj in tools_by_name.values():
        schema = tool_obj.args_schema.model_json_schema() if tool_obj.args_schema else {}
        params = []
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        for pname, pinfo in props.items():
            ptype = pinfo.get("type", "string")
            prefix = "" if pname in required else "?"
            params.append(f"{pname}{prefix}:{ptype}")
        result.append({
            "name": tool_obj.name,
            "description": tool_obj.description.split("\n")[0],
            "parameters": ",".join(params),
        })
    return result


def get_agents_metadata() -> dict:
    """Build agent catalog for discovery API.

    Returns a dict suitable for TOON or JSON encoding.
    """
    agents_list = []
    for name, entry in AGENTS.items():
        agent = entry["agent"]
        agents_list.append({
            "name": name,
            "description": entry["description"],
            "endpoint": "/chat",
            "tools": _extract_tools(agent),
        })
    return {"agents": agents_list}


def get_langfuse_handler(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    app_id: str | None = None,
) -> dict:
    """Return a config dict with Langfuse callback and metadata.

    LANGFUSE_ENABLED=false ise bos dict doner.
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
