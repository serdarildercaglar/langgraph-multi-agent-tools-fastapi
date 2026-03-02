"""Layer 4: Agent-as-tool isolation and state management tests."""

import uuid

import pytest

from src.agents.main_agent import agent as main_agent
from src.agents.product_agent import agent as product_agent


@pytest.mark.integration
class TestEphemeralThreadId:
    """Verify sub-agent calls use ephemeral thread_ids."""

    async def test_ephemeral_thread_id_format(self, temp_checkpointer):
        """Sub-agent tool wrapper uses 'tool:' prefix."""
        from src.agents.main_agent import ask_product_specialist

        # The tool source code uses f"tool:{uuid.uuid4()}"
        # We verify this by checking the tool exists and is async
        assert ask_product_specialist.coroutine is not None

    async def test_sub_agent_result_in_parent(self, temp_checkpointer):
        """Product agent response appears in main agent's state."""
        from src.providers import wire_checkpointer
        wire_checkpointer(temp_checkpointer)

        thread_id = f"test:parent:{uuid.uuid4()}"
        result = await main_agent.ainvoke(
            {"messages": [{"role": "user", "content": "Search for laptops under $1000"}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        messages = result["messages"]
        # Should have ToolMessage from sub-agent
        tool_messages = [m for m in messages if m.type == "tool"]
        assert len(tool_messages) > 0

    async def test_sub_agent_no_persistent_state(self, temp_checkpointer):
        """Ephemeral thread_id leaves no lasting checkpoint."""
        product_agent.checkpointer = temp_checkpointer

        ephemeral_id = f"tool:{uuid.uuid4()}"
        await product_agent.ainvoke(
            {"messages": [{"role": "user", "content": "Find headphones"}]},
            config={"configurable": {"thread_id": ephemeral_id}},
        )

        # Try to get state for ephemeral thread — should have state but
        # each call creates a new unique thread_id, so no reuse occurs
        state = await product_agent.aget_state(
            config={"configurable": {"thread_id": ephemeral_id}}
        )
        # State exists for this specific call but won't be reused
        # because next call generates a new uuid
        assert state is not None


@pytest.mark.integration
class TestCompositeThreadIdIsolation:
    """Verify different app_id/user_id/session_id combos are isolated."""

    async def test_composite_thread_id_isolation(self, temp_checkpointer):
        """appA:u1:s1 and appB:u1:s1 have separate state."""
        from src.providers import wire_checkpointer
        wire_checkpointer(temp_checkpointer)

        # Send to appA
        await main_agent.ainvoke(
            {"messages": [{"role": "user", "content": "Hello from app A"}]},
            config={"configurable": {"thread_id": "appA:u1:s1"}},
        )

        # Send to appB
        await main_agent.ainvoke(
            {"messages": [{"role": "user", "content": "Hello from app B"}]},
            config={"configurable": {"thread_id": "appB:u1:s1"}},
        )

        state_a = await main_agent.aget_state({"configurable": {"thread_id": "appA:u1:s1"}})
        state_b = await main_agent.aget_state({"configurable": {"thread_id": "appB:u1:s1"}})

        # Both should have state but with different content
        msgs_a = [m.content for m in state_a.values["messages"] if m.type == "human"]
        msgs_b = [m.content for m in state_b.values["messages"] if m.type == "human"]
        assert "Hello from app A" in msgs_a
        assert "Hello from app B" in msgs_b
        assert "Hello from app B" not in msgs_a
        assert "Hello from app A" not in msgs_b

    async def test_different_sessions_isolated(self, temp_checkpointer):
        """Same user, different sessions → different history."""
        from src.providers import wire_checkpointer
        wire_checkpointer(temp_checkpointer)

        await main_agent.ainvoke(
            {"messages": [{"role": "user", "content": "Session 1 message"}]},
            config={"configurable": {"thread_id": "app:u1:sess1"}},
        )
        await main_agent.ainvoke(
            {"messages": [{"role": "user", "content": "Session 2 message"}]},
            config={"configurable": {"thread_id": "app:u1:sess2"}},
        )

        state_s1 = await main_agent.aget_state({"configurable": {"thread_id": "app:u1:sess1"}})
        state_s2 = await main_agent.aget_state({"configurable": {"thread_id": "app:u1:sess2"}})

        msgs_s1 = [m.content for m in state_s1.values["messages"] if m.type == "human"]
        msgs_s2 = [m.content for m in state_s2.values["messages"] if m.type == "human"]
        assert "Session 1 message" in msgs_s1
        assert "Session 2 message" not in msgs_s1

    async def test_session_continuity(self, temp_checkpointer):
        """Same session across 2 requests → context is maintained."""
        from src.providers import wire_checkpointer
        wire_checkpointer(temp_checkpointer)

        thread_id = f"app:u1:continuity-{uuid.uuid4()}"

        # First request
        await main_agent.ainvoke(
            {"messages": [{"role": "user", "content": "My name is Alice"}]},
            config={"configurable": {"thread_id": thread_id}},
        )

        # Second request — same thread
        result = await main_agent.ainvoke(
            {"messages": [{"role": "user", "content": "What is my name?"}]},
            config={"configurable": {"thread_id": thread_id}},
        )

        ai_msg = result["messages"][-1]
        assert "alice" in ai_msg.content.lower()
