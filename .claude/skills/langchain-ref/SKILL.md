---
name: langchain-ref
description: LangChain 1.2.10 API reference for create_agent, middleware, tools, checkpointers, and streaming. Use when writing or debugging LangChain agent code.
user-invocable: false
---

# LangChain 1.2.10 Quick Reference

## create_agent

```python
from langchain.agents import create_agent

agent = create_agent(
    model: str | BaseChatModel,              # Required. ChatOpenAI instance or "openai:gpt-5"
    tools: Sequence[BaseTool | Callable],    # @tool decorated functions
    system_prompt: str | None = None,        # Prepended before every LLM call
    middleware: Sequence[AgentMiddleware] = (),
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    name: str | None = None,
    response_format: type | None = None,     # Pydantic model for structured output
    debug: bool = False,
) -> CompiledStateGraph
```

Returns `CompiledStateGraph` with `.invoke()`, `.ainvoke()`, `.stream()`, `.astream()`.

**IMPORTANT:** `create_react_agent` is DEPRECATED. Always use `create_agent` from `langchain.agents`.

## Middleware

```python
from langchain.agents.middleware import before_model, after_model, wrap_model_call, wrap_tool_call
```

### @before_model — runs before each LLM call
```python
@before_model
def my_hook(state, runtime):
    # Return None for no changes
    # Return {"messages": [...]} to update state
    return None
```

### @wrap_model_call — intercepts model execution
```python
@wrap_model_call
async def my_wrapper(request: ModelRequest, handler):
    # request.state, request.system_message, request.tools
    # request.override(model=...) for immutable updates
    return await handler(request)
```

**Not:** Agent'lar `ainvoke`/`astream` ile çağrılıyorsa `async def` + `await handler(request)` zorunlu. Sync `def` kullanılırsa `NotImplementedError: awrap_model_call is not available` hatası alınır.

### Execution order for middleware=[m1, m2, m3]:
- before_*: m1 -> m2 -> m3
- wrap_*: m1 wraps m2 wraps m3 (nested)
- after_*: m3 -> m2 -> m1 (reverse)

## Tools

```python
from langchain.tools import tool

@tool
def my_tool(param: str) -> str:
    """Description for LLM to read.

    Args:
        param: Parameter description.
    """
    return "result"
```

## Message Trimming

```python
from langchain_core.messages.utils import trim_messages
from langchain_core.messages import RemoveMessage

trimmed = trim_messages(
    messages,
    max_tokens=4000,
    token_counter="approximate",  # Fast, no model call
    strategy="last",              # Keep recent messages
    include_system=True,          # Always keep system prompt
    start_on="human",             # Start trimmed sequence on human message
)
```

## Streaming

```python
# Token-level (for SSE)
async for token, metadata in agent.astream(
    {"messages": [...]}, config=config, stream_mode="messages"
):
    print(token.content)

# Step-level
async for chunk in agent.astream(
    {"messages": [...]}, config=config, stream_mode="updates"
):
    print(chunk)
```

## Checkpointers

```python
# AsyncSqliteSaver (persistent)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
checkpointer = AsyncSqliteSaver(conn)
await checkpointer.asetup()

# MemorySaver (in-memory, dev only)
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
```

Wire after creation: `agent.checkpointer = checkpointer`

## Agent Invocation

```python
# Async (preferred)
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "Hello"}]},
    config={"configurable": {"thread_id": "app:user:session"}}
)
answer = result["messages"][-1].content

# With callbacks
config = {
    "configurable": {"thread_id": "..."},
    "callbacks": [langfuse_handler],
    "metadata": {"langfuse_user_id": "user1"},
}
```
