"""Layer 3: Agent creation, tool existence, and tool calling tests."""

import pytest

from src.agents.main_agent import agent as main_agent
from src.agents.order_agent import agent as order_agent
from src.agents.product_agent import agent as product_agent
from src.tools.order_tools import initiate_return, track_order
from src.tools.product_tools import get_product_details, search_products


# --- Agent name ---


def test_main_agent_name():
    assert main_agent.name == "main_agent"


def test_product_agent_name():
    assert product_agent.name == "product_agent"


def test_order_agent_name():
    assert order_agent.name == "order_agent"


# --- Tool existence ---


def _get_tool_names(agent) -> set[str]:
    tools_node = agent.nodes.get("tools")
    if not tools_node or not hasattr(tools_node, "bound"):
        return set()
    return set(tools_node.bound.tools_by_name.keys())


def test_main_agent_tools():
    tools = _get_tool_names(main_agent)
    assert "ask_product_specialist" in tools
    assert "ask_order_specialist" in tools


def test_product_agent_tools():
    tools = _get_tool_names(product_agent)
    assert "search_products" in tools
    assert "get_product_details" in tools
    assert "get_recommendations" in tools


def test_order_agent_tools():
    tools = _get_tool_names(order_agent)
    assert "track_order" in tools
    assert "initiate_return" in tools
    assert "initiate_exchange" in tools
    assert "find_alternative" in tools


# --- Tool direct invocation (mock data, no LLM) ---


def test_search_products_returns_string():
    result = search_products.invoke({"query": "headphones"})
    assert isinstance(result, str)
    assert "Results" in result


def test_get_product_details_returns_string():
    result = get_product_details.invoke({"product_id": "SKU-123"})
    assert isinstance(result, str)
    assert "SKU-123" in result


def test_track_order_returns_string():
    result = track_order.invoke({"order_id": "ORD-123"})
    assert isinstance(result, str)
    assert "ORD-123" in result


def test_initiate_return_returns_string():
    result = initiate_return.invoke({"order_id": "ORD-123", "reason": "defective"})
    assert isinstance(result, str)
    assert "Return initiated" in result


# --- Agent invocation with real LLM ---


@pytest.mark.integration
async def test_product_agent_invoke(temp_checkpointer):
    product_agent.checkpointer = temp_checkpointer
    result = await product_agent.ainvoke(
        {"messages": [{"role": "user", "content": "Search for wireless headphones"}]},
        config={"configurable": {"thread_id": "test:product:1"}},
    )
    ai_msg = result["messages"][-1]
    assert ai_msg.content
    assert len(ai_msg.content) > 0


@pytest.mark.integration
async def test_main_routes_to_product(temp_checkpointer):
    """Main agent routes product question to ask_product_specialist."""
    # Wire all agents with checkpointer
    from src.providers import AGENTS, wire_checkpointer
    wire_checkpointer(temp_checkpointer)

    result = await main_agent.ainvoke(
        {"messages": [{"role": "user", "content": "I'm looking for wireless headphones under $300"}]},
        config={"configurable": {"thread_id": "test:main:product:1"}},
    )
    # Check that a tool was called
    messages = result["messages"]
    tool_calls = [m for m in messages if hasattr(m, "tool_calls") and m.tool_calls]
    assert len(tool_calls) > 0
    tool_names = [tc["name"] for m in tool_calls for tc in m.tool_calls]
    assert "ask_product_specialist" in tool_names


@pytest.mark.integration
async def test_main_routes_to_order(temp_checkpointer):
    """Main agent routes order question to ask_order_specialist."""
    from src.providers import wire_checkpointer
    wire_checkpointer(temp_checkpointer)

    result = await main_agent.ainvoke(
        {"messages": [{"role": "user", "content": "Where is my order ORD-78432? Track it please."}]},
        config={"configurable": {"thread_id": "test:main:order:1"}},
    )
    messages = result["messages"]
    tool_calls = [m for m in messages if hasattr(m, "tool_calls") and m.tool_calls]
    assert len(tool_calls) > 0
    tool_names = [tc["name"] for m in tool_calls for tc in m.tool_calls]
    assert "ask_order_specialist" in tool_names


@pytest.mark.integration
async def test_main_direct_greeting(temp_checkpointer):
    """Main agent answers greetings directly without tools."""
    from src.providers import wire_checkpointer
    wire_checkpointer(temp_checkpointer)

    result = await main_agent.ainvoke(
        {"messages": [{"role": "user", "content": "Hello! How are you?"}]},
        config={"configurable": {"thread_id": "test:main:greet:1"}},
    )
    ai_msg = result["messages"][-1]
    assert ai_msg.content
    # Should NOT have tool calls for a simple greeting
    tool_calls = [m for m in result["messages"] if hasattr(m, "tool_calls") and m.tool_calls]
    assert len(tool_calls) == 0
