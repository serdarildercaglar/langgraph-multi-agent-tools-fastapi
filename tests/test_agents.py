"""Layer 3: Agent creation, tool existence, and tool calling tests."""

import pytest

from src.agents.main_agent import agent as main_agent
from src.agents.billing_agent import agent as billing_agent
from src.agents.subscription_agent import agent as subscription_agent
from src.agents.technical_agent import agent as technical_agent
from src.tools.billing_tools import get_invoice, get_payment_history
from src.tools.subscription_tools import get_current_plan, search_plans
from src.tools.technical_tools import check_network_status, run_line_diagnostic


# --- Agent name ---


def test_main_agent_name():
    assert main_agent.name == "main_agent"


def test_subscription_agent_name():
    assert subscription_agent.name == "subscription_agent"


def test_billing_agent_name():
    assert billing_agent.name == "billing_agent"


def test_technical_agent_name():
    assert technical_agent.name == "technical_agent"


# --- Tool existence ---


def _get_tool_names(agent) -> set[str]:
    tools_node = agent.nodes.get("tools")
    if not tools_node or not hasattr(tools_node, "bound"):
        return set()
    return set(tools_node.bound.tools_by_name.keys())


def test_main_agent_tools():
    tools = _get_tool_names(main_agent)
    assert "ask_subscription_specialist" in tools
    assert "ask_billing_specialist" in tools
    assert "ask_technical_specialist" in tools


def test_subscription_agent_tools():
    tools = _get_tool_names(subscription_agent)
    assert "get_current_plan" in tools
    assert "search_plans" in tools
    assert "compare_plans" in tools
    assert "change_plan" in tools
    assert "add_package" in tools


def test_billing_agent_tools():
    tools = _get_tool_names(billing_agent)
    assert "get_invoice" in tools
    assert "get_payment_history" in tools
    assert "explain_charges" in tools
    assert "initiate_payment_plan" in tools
    assert "suggest_plan_change" in tools


def test_technical_agent_tools():
    tools = _get_tool_names(technical_agent)
    assert "check_network_status" in tools
    assert "run_line_diagnostic" in tools
    assert "check_device_compatibility" in tools
    assert "create_trouble_ticket" in tools


# --- Tool direct invocation (mock data, no LLM) ---


def test_get_current_plan_returns_string():
    result = get_current_plan.invoke({"msisdn": "05321234567"})
    assert isinstance(result, str)
    assert "05321234567" in result


def test_search_plans_returns_string():
    result = search_plans.invoke({"usage_type": "high-data"})
    assert isinstance(result, str)
    assert "Available plans" in result


def test_get_invoice_returns_string():
    result = get_invoice.invoke({"msisdn": "05321234567"})
    assert isinstance(result, str)
    assert "Invoice" in result


def test_get_payment_history_returns_string():
    result = get_payment_history.invoke({"msisdn": "05321234567"})
    assert isinstance(result, str)
    assert "Payment history" in result


def test_check_network_status_returns_string():
    result = check_network_status.invoke({"location": "Istanbul Kadikoy"})
    assert isinstance(result, str)
    assert "Istanbul Kadikoy" in result


def test_run_line_diagnostic_returns_string():
    result = run_line_diagnostic.invoke({"msisdn": "05321234567"})
    assert isinstance(result, str)
    assert "05321234567" in result


# --- Agent invocation with real LLM ---


@pytest.mark.integration
async def test_subscription_agent_invoke(temp_checkpointer):
    subscription_agent.checkpointer = temp_checkpointer
    result = await subscription_agent.ainvoke(
        {"messages": [{"role": "user", "content": "What is my current plan for 05321234567?"}]},
        config={"configurable": {"thread_id": "test:subscription:1"}},
    )
    ai_msg = result["messages"][-1]
    assert ai_msg.content
    assert len(ai_msg.content) > 0


@pytest.mark.integration
async def test_main_routes_to_subscription(temp_checkpointer):
    """Main agent routes plan question to ask_subscription_specialist."""
    from src.providers import wire_checkpointer
    wire_checkpointer(temp_checkpointer)

    result = await main_agent.ainvoke(
        {"messages": [{"role": "user", "content": "I want to change my plan to something with more data"}]},
        config={"configurable": {"thread_id": "test:main:subscription:1"}},
    )
    messages = result["messages"]
    tool_calls = [m for m in messages if hasattr(m, "tool_calls") and m.tool_calls]
    assert len(tool_calls) > 0
    tool_names = [tc["name"] for m in tool_calls for tc in m.tool_calls]
    assert "ask_subscription_specialist" in tool_names


@pytest.mark.integration
async def test_main_routes_to_billing(temp_checkpointer):
    """Main agent routes billing question to ask_billing_specialist."""
    from src.providers import wire_checkpointer
    wire_checkpointer(temp_checkpointer)

    result = await main_agent.ainvoke(
        {"messages": [{"role": "user", "content": "Why is my last invoice so high? Show me the charges."}]},
        config={"configurable": {"thread_id": "test:main:billing:1"}},
    )
    messages = result["messages"]
    tool_calls = [m for m in messages if hasattr(m, "tool_calls") and m.tool_calls]
    assert len(tool_calls) > 0
    tool_names = [tc["name"] for m in tool_calls for tc in m.tool_calls]
    assert "ask_billing_specialist" in tool_names


@pytest.mark.integration
async def test_main_routes_to_technical(temp_checkpointer):
    """Main agent routes technical issue to ask_technical_specialist."""
    from src.providers import wire_checkpointer
    wire_checkpointer(temp_checkpointer)

    result = await main_agent.ainvoke(
        {"messages": [{"role": "user", "content": "My internet is not working, I have no signal at all"}]},
        config={"configurable": {"thread_id": "test:main:technical:1"}},
    )
    messages = result["messages"]
    tool_calls = [m for m in messages if hasattr(m, "tool_calls") and m.tool_calls]
    assert len(tool_calls) > 0
    tool_names = [tc["name"] for m in tool_calls for tc in m.tool_calls]
    assert "ask_technical_specialist" in tool_names


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
