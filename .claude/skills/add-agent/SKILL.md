---
name: add-agent
description: Add a new agent to the project following the 4-step template pattern. Use when creating new agents, specialist agents, or domain-specific agents.
argument-hint: "[domain-name]"
---

# Add New Agent

Create a new agent for the domain `$ARGUMENTS` following the project's strict 4-step pattern.

## Pre-flight Checks

Before starting, verify:
1. The domain name is lowercase, no spaces (e.g., `shipping`, `payment`, `inventory`)
2. No existing agent with the same name in `src/agents/`
3. No circular import will be introduced

## Step 1: Create Tools File

Create `src/tools/{domain}_tools.py`:

```python
from langchain.tools import tool


@tool
def example_tool(param: str) -> str:
    """One-line description visible in discovery API.

    Args:
        param: Clear parameter description.
    """
    return "result"
```

**Rules:**
- Import `tool` from `langchain.tools` (NOT `langchain_core.tools`)
- Each `@tool` function must have a docstring with one-line summary + Args section
- Return type is always `str`
- Pure functions preferred, no side effects unless calling real backend
- One file per domain, multiple tools per file OK

## Step 2: Create Agent File

Create `src/agents/{domain}_agent.py`:

```python
from langchain.agents import create_agent

from src.config.llm import llm
from src.config.settings import settings
from src.middleware.trim import trim_old_messages
from src.tools.{domain}_tools import tool1, tool2

_middleware = [trim_old_messages]
if settings.langfuse_prompt_management_enabled:
    from src.middleware.prompt import langfuse_prompt

    _middleware.insert(0, langfuse_prompt)

agent = create_agent(
    model=llm,
    tools=[tool1, tool2],
    middleware=_middleware,
    system_prompt=(
        "You are a {domain} specialist. "
        "Describe the agent's role and behavior clearly."
    ),
    name="{domain}_agent",
)
```

**Critical Rules:**
- `from langchain.agents import create_agent` — NEVER use `create_react_agent`
- Import `llm` from `src.config.llm` — NEVER create a new ChatOpenAI instance
- Always include `trim_old_messages` in middleware
- `langfuse_prompt` middleware conditional on `settings.langfuse_prompt_management_enabled`
- NEVER pass `checkpointer` parameter — it's wired at lifespan
- Module-level assignment: `agent = create_agent(...)` — NO factory/wrapper functions
- `name` parameter: lowercase snake_case matching the filename — **this name is also the Langfuse prompt name**

## Step 3: Register in providers.py

Add to `src/providers.py`:

1. Add import at the top (maintain alphabetical order):
```python
from src.agents.{domain}_agent import agent as {domain}_agent
```

2. Add entry to AGENTS dict:
```python
AGENTS = {
    # ... existing entries
    "{domain}": {
        "agent": {domain}_agent,
        "description": "Short, clear description for discovery API.",
    },
}
```

**Rules:**
- Key in AGENTS dict = the `agent_name` used in API requests
- Description is shown in `GET /agents` discovery endpoint
- Tool metadata is extracted automatically from the compiled agent — no manual tool listing needed

## Step 4: Verify

After creating the agent:
1. Check import chain: config -> middleware -> tools -> agents -> providers (NO circular imports)
2. Ensure `GET /agents` will list the new agent with correct tools
3. API call: `POST /chat` with `"agent_name": "{domain}"` should work

## If This Agent Calls Other Agents (Agent-as-Tool)

When the new agent needs to delegate to another agent:

```python
import uuid
from langchain.tools import tool
from src.agents.other_agent import agent as other_agent


@tool
async def ask_other_specialist(question: str) -> str:
    """Delegate to other specialist for specific queries.

    Args:
        question: The question to delegate.
    """
    result = await other_agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"tool:{uuid.uuid4()}"}},
    )
    return result["messages"][-1].content
```

**Rules for agent-as-tool:**
- Tool function MUST be `async def`
- Use `await agent.ainvoke()` (not `invoke`)
- Ephemeral thread_id: `f"tool:{uuid.uuid4()}"` — single-use, no persistent state
- Extract result: `result["messages"][-1].content`
- Place agent-as-tool wrappers in the calling agent's file, not in tools/

## Step 5: Create Prompt in Langfuse (if prompt management enabled)

When `LANGFUSE_PROMPT_MANAGEMENT_ENABLED=true`:

1. Go to Langfuse UI → Prompts → Create
2. **Name**: must match `create_agent(name=...)` value exactly (e.g., `{domain}_agent`)
3. **Type**: Text (not Chat)
4. **Content**: paste the `system_prompt` string from the agent file
5. **Label**: assign `production` label

The `@wrap_model_call` middleware (`langfuse_prompt`) will:
- Detect agent name via `get_config()["metadata"]["lc_agent_name"]`
- Fetch the matching Langfuse prompt (60s cache TTL, stale-while-revalidate)
- Override `system_message` via `request.override()`
- Fall back to hardcoded `system_prompt` if Langfuse is unreachable

Convention: **Langfuse prompt name = `create_agent(name=...)` value**

## Forbidden Actions

- DO NOT modify `src/models/schemas.py`
- DO NOT add hardcoded config defaults — use `.env`
- DO NOT create factory functions (build_*, make_*, create_* wrappers)
- DO NOT use `create_react_agent` (deprecated)
- DO NOT import from `langchain_core.tools`
